"""Conservative, evidence-backed cross-camera fire association proposals.

An accepted proposal remains an operator-review candidate, never a confirmed target.
The geometric check is a planar image consistency test, not camera calibration.
"""
import base64
import itertools
import json
import math
import re
import time

import cv2
import numpy as np
import requests

from . import config

PROMPT_ID = 'astra_fire_association_v1'
INSTRUCTIONS = '''Compare the annotated CCTV frames for the SAME physical location and SAME physical fires.
The images may show unrelated scenes. IDs are arbitrary and rectangles are tentative observations, not
proof of identity. Do not match because IDs, image ordering, fire count, flame color or generic pallets
look similar. Find distinctive persistent shared background landmarks and a coherent viewpoint orientation
before proposing a correspondence. Architectural differences, missing shared anchors, ambiguous fire
bases, and possible non-overlap require abstention. Describe the actual landmarks and orientation for
any candidate. Never invent IDs. A group may contain at most one ID per view. Return all other IDs in
unmatched. Only set room_status verified if room identity and viewpoint relationship are well supported.
For uncertain or contradictory room identity, return no candidates. The uncertainties array must contain
only unresolved facts that affect room or proposed fire identity, not unrelated questions such as why a
frame is offset. Do not claim metric calibration.'''

_SCHEMA = {
    'type': 'object', 'additionalProperties': False,
    'properties': {
        'room_status': {'type': 'string', 'enum': ['verified', 'unverified', 'contradicted']},
        'evidence': {'type': 'array', 'items': {'type': 'string'}},
        'uncertainties': {'type': 'array', 'items': {'type': 'string'}},
        'candidates': {'type': 'array', 'items': {
            'type': 'object', 'additionalProperties': False,
            'properties': {
                'members': {'type': 'array', 'items': {'type': 'string'}},
                'shared_landmarks': {'type': 'string'}, 'orientation_evidence': {'type': 'string'},
                'confidence': {'type': 'string', 'enum': ['low', 'medium', 'high']},
            }, 'required': ['members', 'shared_landmarks', 'orientation_evidence', 'confidence']}},
        'unmatched': {'type': 'array', 'items': {
            'type': 'object', 'additionalProperties': False,
            'properties': {'id': {'type': 'string'}, 'reason': {'type': 'string'}},
            'required': ['id', 'reason']}},
    }, 'required': ['room_status', 'evidence', 'uncertainties', 'candidates', 'unmatched'],
}


def _sources(views, paths):
    if len(views) != len(paths) or not 2 <= len(views) <= 3:
        raise ValueError('association requires two or three views and one frame per view')
    result, images = {}, {}
    for view, path in zip(views, paths):
        vid = view.get('view_id')
        if not isinstance(vid, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,40}', vid) or vid in images:
            raise ValueError('invalid or duplicate view ID')
        im = cv2.imread(str(path))
        if im is None:
            raise ValueError('cannot read association frame')
        images[vid] = im
        for fire in view['observations']['fire_sources']:
            if not isinstance(fire, dict):
                raise ValueError('invalid source')
            fid = fire.get('id')
            if 'frame_t_s' not in view:
                # Legacy callers explicitly bind bbox_normalized to the supplied image.
                box = fire.get('bbox_normalized')
            else:
                timestamp = view['frame_t_s']
                if isinstance(timestamp, bool) or not isinstance(timestamp, (int, float)) or not math.isfinite(timestamp):
                    raise ValueError('invalid selected frame timestamp')
                frame_boxes = fire.get('bbox_by_frame', [])
                if not isinstance(frame_boxes, list):
                    raise ValueError('invalid per-frame boxes')
                exact = [entry for entry in frame_boxes if isinstance(entry, dict)
                         and isinstance(entry.get('t_s'), (int, float)) and not isinstance(entry.get('t_s'), bool)
                         and entry['t_s'] == timestamp]
                if len(exact) > 1:
                    raise ValueError('duplicate boxes for selected timestamp')
                if exact:
                    box = exact[0].get('bbox_normalized')
                elif (isinstance(fire.get('bbox_at_s'), (int, float))
                      and not isinstance(fire.get('bbox_at_s'), bool) and fire['bbox_at_s'] == timestamp):
                    box = fire.get('bbox_normalized')
                else:
                    box = None
            if not isinstance(fid, str) or not re.fullmatch(r'[A-Za-z0-9_:\-]{1,100}', fid) or fid in result:
                raise ValueError('invalid or duplicate source ID')
            if box is not None and (not isinstance(box, (list, tuple)) or len(box) != 4 or any(
                isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) for x in box
            ) or not (0 <= box[0] < box[2] <= 1 and 0 <= box[1] < box[3] <= 1)):
                raise ValueError('invalid normalized fire box')
            result[fid] = {'view_id': vid, 'box': tuple(box) if box is not None else None}
    return result, images


def _annotated(im, items):
    img = im.copy()
    h, w = img.shape[:2]
    for fid, source in items:
        x1, y1, x2, y2 = source['box']
        p1, p2 = (int(x1*w), int(y1*h)), (min(w-1, int(x2*w)), min(h-1, int(y2*h)))
        cv2.rectangle(img, p1, p2, (255, 220, 0), 2)
        label = fid[:100]
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, .45, 1)
        # Keep text visible even at the top edge; annotations are not used for feature registration.
        y = max(th+4, min(h-2, p1[1]-3))
        cv2.rectangle(img, (p1[0], y-th-3), (min(w-1, p1[0]+tw+4), min(h-1,y+3)), (0, 0, 0), -1)
        cv2.putText(img, label, (p1[0]+2, y), cv2.FONT_HERSHEY_SIMPLEX, .45, (255,255,255), 1, cv2.LINE_AA)
    ok, encoded = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, 90])
    if not ok:
        raise ValueError('could not encode association frame')
    return 'data:image/jpeg;base64,' + base64.b64encode(encoded.tobytes()).decode('ascii')


def _mask(im, items):
    h, w = im.shape[:2]
    mask = np.full((h,w), 255, dtype=np.uint8)
    for _, source in items:
        x1, y1, x2, y2 = source['box']
        # Exclude fire, glow, and some adjacent smoke from background feature matching.
        margin_x, margin_y = (x2-x1)*.3, (y2-y1)*.5
        a = (max(0,int((x1-margin_x)*w)), max(0,int((y1-margin_y)*h)))
        b = (min(w-1,int((x2+margin_x)*w)), min(h-1,int((y2+margin_y)*h)))
        cv2.rectangle(mask,a,b,0,-1)
    return mask


def _registration(vid_a, vid_b, sources, images):
    """Return conservative pixel homography and support details, or None."""
    a, b = images[vid_a], images[vid_b]
    if not hasattr(cv2, 'SIFT_create'):
        return None
    detector = cv2.SIFT_create(nfeatures=2500)
    ka, da = detector.detectAndCompute(cv2.cvtColor(a,cv2.COLOR_BGR2GRAY), _mask(a,[(i,s) for i,s in sources.items() if s['view_id']==vid_a]))
    kb, db = detector.detectAndCompute(cv2.cvtColor(b,cv2.COLOR_BGR2GRAY), _mask(b,[(i,s) for i,s in sources.items() if s['view_id']==vid_b]))
    if da is None or db is None or len(da) < 12 or len(db) < 12:
        return None
    pairs = cv2.BFMatcher().knnMatch(da, db, k=2)
    good = [p[0] for p in pairs if len(p)==2 and p[0].distance < .7*p[1].distance]
    if len(good) < 12:
        return None
    pa = np.float32([ka[m.queryIdx].pt for m in good]); pb = np.float32([kb[m.trainIdx].pt for m in good])
    H, inliers = cv2.findHomography(pa, pb, cv2.RANSAC, 3.0)
    if H is None or inliers is None or not np.isfinite(H).all():
        return None
    keep = inliers.ravel().astype(bool); n = int(keep.sum())
    if n < 12 or n / len(good) < .5:
        return None
    # Inliers must span a substantial part of BOTH pictures, not one textured shelf patch.
    coverage_a = cv2.contourArea(cv2.convexHull(pa[keep])) / (a.shape[0]*a.shape[1])
    coverage_b = cv2.contourArea(cv2.convexHull(pb[keep])) / (b.shape[0]*b.shape[1])
    if min(coverage_a, coverage_b) < .08:
        return None
    return H, {'inliers': n, 'inlier_ratio': round(n/len(good),3),
               'coverage': [round(coverage_a,3), round(coverage_b,3)]}


def _geometry(members, sources, images):
    checks=[]
    for id_a, id_b in itertools.combinations(members,2):
        a,b=sources[id_a],sources[id_b]; va,vb=a['view_id'],b['view_id']
        reg = _registration(va,vb,sources,images)
        if reg is None:
            return None
        H, stats = reg; ah,aw=images[va].shape[:2]; bh,bw=images[vb].shape[:2]
        # Lower box center estimates the fire base. This is only a projective consistency check.
        x1,y1,x2,y2=a['box']; pt=np.float32([[[(x1+x2)*aw/2,y2*ah]]])
        projected=cv2.perspectiveTransform(pt,H)[0,0]
        q1,r1,q2,r2=b['box']; target=np.array([(q1+q2)*bw/2,r2*bh])
        dist=float(np.linalg.norm(projected-target)); tolerance=max(.035*math.hypot(bw,bh), (q2-q1)*bw*.6)
        if not np.isfinite(projected).all() or dist > tolerance:
            return None
        checks.append({'members':[id_a,id_b], 'projected_base_error_px':round(dist,2),
                       'tolerance_px':round(tolerance,2), **stats})
    return checks


def _distinctive_landmark(text):
    # Reject purely generic fire/warehouse descriptions. This lexical gate cannot prove
    # that the model's claimed landmark exists; geometry and human review are still required.
    generic = {'the','a','an','and','or','with','in','on','at','of','by','from','to','is','are',
               'both','same','each','view','views','image','images','their','near','next','behind',
               'fire','fires','flame','flames','smoke','orange','bright','burning','pallet','pallets',
               'warehouse','room','floor','concrete','shelf','shelves','shelving','rack','racks',
               'box','boxes','carton','cartons','object','objects','wall','walls','visible','position'}
    terms = set(re.findall(r'[a-z]+', text.lower())) - generic
    return len(terms) >= 2


def _validate(data, sources, images):
    if not isinstance(data,dict) or set(data) != {'room_status','evidence','uncertainties','candidates','unmatched'}:
        raise ValueError('invalid association response fields')
    room=data['room_status']
    if room not in ('verified','unverified','contradicted'):
        raise ValueError('invalid room status')
    for key in ('evidence','uncertainties'):
        if not isinstance(data[key],list) or any(not isinstance(x,str) or not x.strip() for x in data[key]):
            raise ValueError('invalid room evidence')
    if not isinstance(data['candidates'],list) or not isinstance(data['unmatched'],list):
        raise ValueError('invalid association lists')
    used=set(); proposals=[]
    for c in data['candidates']:
        if not isinstance(c,dict) or set(c) != {'members','shared_landmarks','orientation_evidence','confidence'}:
            raise ValueError('invalid candidate')
        ids=c['members']
        if not isinstance(ids,list) or len(ids)<2 or any(not isinstance(i,str) or i not in sources for i in ids) or len(set(ids))!=len(ids):
            raise ValueError('invalid candidate IDs')
        if used.intersection(ids) or len({sources[i]['view_id'] for i in ids}) != len(ids):
            raise ValueError('duplicate or same-view association')
        used.update(ids)
        if c['confidence'] not in ('low','medium','high') or any(not isinstance(c[k],str) or len(c[k].strip())<12 for k in ('shared_landmarks','orientation_evidence')):
            raise ValueError('candidate lacks landmark or orientation evidence')
        # Basic negative evidence guard, not a semantic proof that a phrase is correct.
        if not _distinctive_landmark(c['shared_landmarks']):
            raise ValueError('candidate landmarks are generic')
        if any(re.search(r'\b(?:matching|same|identical|corresponding)\s+(?:id|ids|identifiers?|numbers?|counts?|order)\b', c[k], re.I) for k in ('shared_landmarks','orientation_evidence')):
            raise ValueError('candidate relies on IDs, count or ordering')
        if any(re.search(r'\b(?:uncertain|unknown|unverified|no (?:shared|distinctive)|cannot|not (?:sure|visible|verified))\b', c[k], re.I) for k in ('shared_landmarks','orientation_evidence')):
            raise ValueError('candidate evidence explicitly uncertain')
        proposals.append(c)
    unmatched=[]
    for item in data['unmatched']:
        if not isinstance(item,dict) or set(item)!={'id','reason'} or item['id'] not in sources or item['id'] in used or not isinstance(item['reason'],str) or not item['reason'].strip():
            raise ValueError('invalid unmatched source')
        used.add(item['id']); unmatched.append(item)
    if used != set(sources):
        raise ValueError('response does not account for every source')
    if room != 'verified' or data['uncertainties'] or not data['evidence']:
        return [], [{'id':i,'reason':'Room or candidate correspondence is not verified.'} for i in sources], ['Room correspondence or evidence is uncertain.']
    accepted=[]; rejected=[]
    for c in proposals:
        check=_geometry(c['members'],sources,images) if c['confidence'] != 'low' else None
        if not check:
            rejected.extend({'id':i,'reason':'Background registration or projected fire-base consistency was insufficient.'} for i in c['members'])
        else:
            accepted.append({'members':c['members'], 'reason':c['shared_landmarks']+'; '+c['orientation_evidence'],
                             'shared_landmarks':c['shared_landmarks'], 'orientation_evidence':c['orientation_evidence'],
                             'confidence':c['confidence'], 'geometry_checks':check})
    return accepted, unmatched+rejected, (['One or more candidates failed independent image geometry checks.'] if rejected else [])


def _redact_response(value, secret):
    if isinstance(value, dict):
        sensitive = {'authorization', 'api_key', 'access_token', 'bearer_token'}
        return {k: '[redacted]' if str(k).lower() in sensitive else _redact_response(v, secret) for k,v in value.items()}
    if isinstance(value, list):
        return [_redact_response(v, secret) for v in value]
    if isinstance(value, str) and secret:
        return value.replace(secret, '[redacted]')
    return value


@config.weave_op
def propose(views, frame_paths):
    """Return API visual proposals with evidence and explicit abstention; never confirm targets."""
    t=time.monotonic()
    result={'status':'manual_review','candidates':[],'raw_text':'','content':'','reasoning_content':'',
            'prompt_id':PROMPT_ID,'model_id':None,'requested_model_id':config.ASTRA_MODEL,
            'provider_response':None,'latency_s':0,'error':None,
            'room_status':'unverified','unmatched':[],'evidence':[],'uncertainties':[]}
    try:
        sources,images=_sources(views,frame_paths)
        result['unmatched']=[{'id':i,'reason':'Association not established.'} for i in sources]
        if not sources:
            raise ValueError('no observations to associate')
        invisible = [{'id': i, 'reason': 'No box at the selected frame timestamp.'}
                     for i, source in sources.items() if source['box'] is None]
        visible = {i: source for i, source in sources.items() if source['box'] is not None}
        result['unmatched'] = invisible + [{'id': i, 'reason': 'Association not established.'} for i in visible]
        if len({s['view_id'] for s in visible.values()}) < 2:
            result['uncertainties'] = ['Fewer than two views contain observations at their selected frame timestamps.']
            result['latency_s'] = round(time.monotonic()-t,2)
            return result
        token=config.get('OPENAI_API_KEY')
        if not token:
            raise ValueError('OPENAI_API_KEY not configured')
        content=[]
        for vid,im in images.items():
            items=[(i,s) for i,s in visible.items() if s['view_id']==vid]
            content.extend([{'type':'input_text','text':'View '+vid+'; exact visible ID labels: '+json.dumps([i for i,_ in items])},
                            {'type':'input_image','image_url':_annotated(im,items),'detail':'high'}])
        payload={'model':config.ASTRA_MODEL,'instructions':INSTRUCTIONS,'input':[{'role':'user','content':content}],
                 'reasoning':{'effort':'medium'},'max_output_tokens':5000,'store':False,
                 'text':{'format':{'type':'json_schema','name':'fire_association','strict':True,'schema':_SCHEMA}}}
        r=requests.post('https://api.openai.com/v1/responses',json=payload,
                        headers={'Authorization':'Bearer '+token},timeout=config.ASTRA_TIMEOUT_S)
        if r.status_code != 200:
            raise ValueError('Astra API returned HTTP '+str(r.status_code))
        try:
            response=r.json()
        except ValueError:
            result['raw_text'] = _redact_response(getattr(r, 'text', ''), token)
            raise ValueError('malformed Astra JSON response')
        result['provider_response'] = _redact_response(response, token)
        result['raw_text'] = json.dumps(result['provider_response'], ensure_ascii=False)
        if not isinstance(response, dict):
            raise ValueError('malformed Astra response')
        model = response.get('model')
        if not isinstance(model, str) or not model.startswith('gpt-6-astra') or response.get('status') != 'completed':
            raise ValueError('Astra response incomplete or unexpected model')
        result['model_id'] = model
        output = response.get('output')
        if not isinstance(output, list) or any(not isinstance(o, dict) for o in output):
            raise ValueError('malformed Astra output')
        chunks=[]
        for item in output:
            content_blocks = item.get('content', [])
            if not isinstance(content_blocks, list) or any(not isinstance(c, dict) for c in content_blocks):
                raise ValueError('malformed Astra content')
            for block in content_blocks:
                if block.get('type') == 'output_text':
                    text = block.get('text')
                    if not isinstance(text, str):
                        raise ValueError('malformed Astra text')
                    chunks.append(text)
        content='\n'.join(chunks)
        result['content']=_redact_response(content,token)
        if result['content']:
            result['raw_text']=result['content']
        data=json.loads(content)
        candidates, unmatched, errors = _validate(data,visible,images)
        unmatched = invisible + unmatched
        result.update(room_status=data['room_status'],evidence=data['evidence'],uncertainties=data['uncertainties']+errors,
                      candidates=candidates,unmatched=unmatched,status='proposed' if candidates else 'manual_review')
    except (ValueError,KeyError,TypeError,IndexError,requests.RequestException,cv2.error) as e:
        result['error']='Association unavailable or unverified: '+type(e).__name__+': '+str(e)[:200]
        result['candidates']=[]
    result['latency_s']=round(time.monotonic()-t,2)
    return result
