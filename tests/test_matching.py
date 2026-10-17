import copy

import cv2
import numpy as np
import pytest

from scene2real import matching


def fixture():
    # A projective test image with textured background; no claim of true 3D calibration.
    rng=np.random.default_rng(319)
    a=rng.integers(0,256,(400,600,3),dtype=np.uint8)
    a=cv2.GaussianBlur(a,(3,3),0)
    H=np.array([[1,0,8],[0,1,6],[0,0,1]],dtype=float)
    b=cv2.warpPerspective(a,H,(600,400))
    sources={'V1:A9':{'view_id':'V1','box':(.30,.35,.37,.48)},
             'V2:B2':{'view_id':'V2','box':(.30+8/600,.35+6/400,.37+8/600,.48+6/400)}}
    data={'room_status':'verified','evidence':['Distinct striped cabinet and corner joint are visible across both views.'],
          'uncertainties':[], 'candidates':[{'members':['V1:A9','V2:B2'],
          'shared_landmarks':'Striped cabinet next to a marked column',
          'orientation_evidence':'Column remains to the left of the cabinet from both views',
          'confidence':'high'}], 'unmatched':[]}
    return sources,{'V1':a,'V2':b},data


def test_projective_positive_and_permutation():
    sources,images,data=fixture()
    candidates,unmatched,warnings=matching._validate(data,sources,images)
    assert len(candidates)==1 and not unmatched and not warnings
    assert candidates[0]['geometry_checks'][0]['inliers'] >= 12
    data['candidates'][0]['members'].reverse()
    candidates,unmatched,warnings=matching._validate(data,dict(reversed(list(sources.items()))),images)
    assert len(candidates)==1 and not unmatched and not warnings


def test_rejects_reused_or_same_view_and_unknown_ids():
    sources,images,data=fixture()
    for members in (['V1:A9','V1:A9'],['V1:A9','V9:fake']):
        bad=copy.deepcopy(data); bad['candidates'][0]['members']=members
        with pytest.raises(ValueError): matching._validate(bad,sources,images)
    bad=copy.deepcopy(data); bad['candidates']*=2
    with pytest.raises(ValueError): matching._validate(bad,sources,images)
    same=copy.deepcopy(sources); same['V2:B2']['view_id']='V1'
    with pytest.raises(ValueError): matching._validate(data,same,images)


def test_requires_accounting_and_nonempty_evidence():
    sources,images,data=fixture()
    bad=copy.deepcopy(data); bad['candidates'][0]['orientation_evidence']=''
    with pytest.raises(ValueError): matching._validate(bad,sources,images)
    bad=copy.deepcopy(data); bad['unmatched']=[{'id':'V1:A9','reason':'unknown'}]
    with pytest.raises(ValueError): matching._validate(bad,sources,images)
    bad=copy.deepcopy(data); bad['candidates']=[]
    with pytest.raises(ValueError): matching._validate(bad,sources,images)


@pytest.mark.parametrize('field,value',[('room_status','unverified'),('room_status','contradicted'),('uncertainties',['camera relation unknown']),('evidence',[])])
def test_uncertain_room_never_returns_candidates(field,value):
    sources,images,data=fixture(); data[field]=value
    candidates,unmatched,warnings=matching._validate(data,sources,images)
    assert not candidates and {x['id'] for x in unmatched}==set(sources) and warnings


def test_disjoint_views_and_misaligned_fire_bases_abstain():
    sources,images,data=fixture(); images['V2']=np.zeros_like(images['V2'])
    candidates,unmatched,warnings=matching._validate(data,sources,images)
    assert not candidates and len(unmatched)==2 and warnings
    sources,images,data=fixture(); sources['V2:B2']['box']=(.7,.3,.8,.45)
    candidates,unmatched,warnings=matching._validate(data,sources,images)
    assert not candidates and len(unmatched)==2 and warnings


def test_provider_failure_is_manual_and_does_not_expose_secrets(tmp_path,monkeypatch):
    sources,images,_=fixture()
    p=[]
    for name in ('V1','V2'):
        path=tmp_path/(name+'.jpg'); cv2.imwrite(str(path),images[name]); p.append(path)
    views=[{'view_id':v,'observations':{'fire_sources':[{'id':i,'bbox_normalized':s['box']} for i,s in sources.items() if s['view_id']==v]}} for v in ('V1','V2')]
    monkeypatch.setattr(matching.config,'get',lambda key: 'secret-for-test')
    class Response: status_code=503
    monkeypatch.setattr(matching.requests,'post',lambda *a,**k: Response())
    result=matching.propose(views,p)
    assert result['status']=='manual_review' and not result['candidates'] and len(result['unmatched'])==2
    assert 'secret-for-test' not in str(result)


def test_generic_landmarks_cannot_justify_a_match():
    sources,images,data=fixture()
    data['candidates'][0]['shared_landmarks']='Orange flames on pallets in a warehouse'
    with pytest.raises(ValueError,match='generic'):
        matching._validate(data,sources,images)


def test_identifier_order_is_not_identity_evidence():
    sources,images,data=fixture()
    data['candidates'][0]['orientation_evidence']='The same IDs identify the corresponding burning sites.'
    with pytest.raises(ValueError,match='IDs'):
        matching._validate(data,sources,images)


def _timestamped_views_and_paths(tmp_path):
    sources,images,data=fixture(); views=[]; paths=[]
    for vid in ('V1','V2'):
        path=tmp_path/(vid+'.jpg'); cv2.imwrite(str(path),images[vid]); paths.append(path)
        sid=next(i for i,s in sources.items() if s['view_id']==vid)
        box=sources[sid]['box']
        fires=[{'id':sid,'bbox_normalized':box,'bbox_at_s':2.0,
                'bbox_by_frame':[{'t_s':2.0,'bbox_normalized':box}]},
               {'id':vid+':missing','bbox_normalized':(.1,.1,.2,.2),
                'bbox_at_s': 1.0 if vid=='V1' else 3.0,
                'bbox_by_frame':[{'t_s':1.0 if vid=='V1' else 3.0,'bbox_normalized':(.1,.1,.2,.2)}]}]
        views.append({'view_id':vid,'frame_t_s':2.0,'observations':{'fire_sources':fires}})
    return views,paths,data


def test_selected_middle_uses_only_exact_frame_and_accounts_for_absent(tmp_path,monkeypatch):
    import json
    views,paths,data=_timestamped_views_and_paths(tmp_path); calls=[]
    monkeypatch.setattr(matching.config,'get',lambda key:'test')
    class Response:
        status_code=200
        def json(self):
            return {'model':'gpt-6-astra','status':'completed','output':[{'type':'message','content':[{'type':'output_text','text':json.dumps(data)}]}]}
    def send(*a,**kw): calls.append(kw['json']); return Response()
    monkeypatch.setattr(matching.requests,'post',send)
    result=matching.propose(views,paths)
    assert result['status']=='proposed' and result['candidates'][0]['members']==['V1:A9','V2:B2']
    assert {x['id'] for x in result['unmatched']}=={'V1:missing','V2:missing'}
    assert all('selected frame' in x['reason'] for x in result['unmatched'])
    text=' '.join(c['text'] for c in calls[0]['input'][0]['content'] if c['type']=='input_text')
    assert 'V1:missing' not in text and 'V2:missing' not in text


def test_no_two_visible_views_skips_model_and_never_uses_nearest(tmp_path,monkeypatch):
    views,paths,_=_timestamped_views_and_paths(tmp_path)
    views[0]['frame_t_s']=2.0000001  # Close is not the same sampled instant.
    monkeypatch.setattr(matching.requests,'post',lambda *a,**k: pytest.fail('must not call model'))
    result=matching.propose(views,paths)
    assert result['status']=='manual_review' and not result['candidates']
    assert {x['id'] for x in result['unmatched']}=={'V1:A9','V1:missing','V2:B2','V2:missing'}
    assert 'Fewer than two views' in result['uncertainties'][0]


@pytest.mark.parametrize('body',[[],{'model':None}, {'model':2,'status':'completed'},
  {'model':'gpt-6-astra','status':'completed','output':{}},
  {'model':'gpt-6-astra','status':'completed','output':[{'content':[None]}]},
  {'model':'gpt-6-astra','status':'completed','output':[{'content':[{'type':'output_text','text':None}]}]}])
def test_malformed_api_body_fails_closed(tmp_path,monkeypatch,body):
    views,paths,_=_timestamped_views_and_paths(tmp_path)
    monkeypatch.setattr(matching.config,'get',lambda key:'test')
    class Response:
        status_code=200
        def json(self): return body
    monkeypatch.setattr(matching.requests,'post',lambda *a,**k:Response())
    result=matching.propose(views,paths)
    assert result['status']=='manual_review' and not result['candidates'] and result['error']
    assert len(result['unmatched'])==4


def test_exact_reference_timestamp_fallback_and_other_time_exclusion(tmp_path):
    views,paths,_=_timestamped_views_and_paths(tmp_path)
    visible=views[0]['observations']['fire_sources'][0]
    visible['bbox_by_frame']=[]  # Explicit legacy reference is tied to this exact sample.
    items,_=matching._sources(views,paths)
    assert items['V1:A9']['box']==tuple(visible['bbox_normalized'])
    views[0]['frame_t_s']=1.5
    items,_=matching._sources(views,paths)
    assert items['V1:A9']['box'] is None


@pytest.mark.parametrize('model_field',[{}, {'model':None}, {'model':''}])
def test_missing_explicit_provider_model_fails_without_false_provenance(tmp_path,monkeypatch,model_field):
    views,paths,_=_timestamped_views_and_paths(tmp_path)
    monkeypatch.setattr(matching.config,'get',lambda key:'key-for-test')
    body={'status':'completed','output':[],**model_field,'provider_note':'key-for-test','authorization':'key-for-test'}
    class Response:
        status_code=200
        def json(self): return body
    monkeypatch.setattr(matching.requests,'post',lambda *a,**k:Response())
    result=matching.propose(views,paths)
    assert result['status']=='manual_review' and result['model_id'] is None and not result['candidates']
    assert result['requested_model_id']==matching.config.ASTRA_MODEL
    assert result['provider_response']['provider_note']=='[redacted]'
    assert result['provider_response']['authorization']=='[redacted]'
    assert result['raw_text'] and 'key-for-test' not in str(result)


@pytest.mark.parametrize('body',[
    'not an envelope', None, [None],
    {'model':'gpt-6-astra','status':'completed','output':None},
    {'model':'gpt-6-astra','status':'completed','output':[None]},
    {'model':'gpt-6-astra','status':'completed','output':[{'content':None}]},
    {'model':'gpt-6-astra','status':'completed','output':[{'content':[None]}]},
])
def test_malformed_envelopes_retained_safely(tmp_path,monkeypatch,body):
    views,paths,_=_timestamped_views_and_paths(tmp_path)
    monkeypatch.setattr(matching.config,'get',lambda key:'secret')
    class Response:
        status_code=200
        def json(self): return body
    monkeypatch.setattr(matching.requests,'post',lambda *a,**k:Response())
    result=matching.propose(views,paths)
    assert result['status']=='manual_review' and not result['candidates'] and result['error']
    assert result['provider_response']==body and result['raw_text']
