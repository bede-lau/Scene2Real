import copy
import json
from pathlib import Path

import pytest
import requests

from scene2real import grounding


@pytest.fixture
def frames(tmp_path):
    p = tmp_path / 'frame.jpg'
    p.write_bytes(b'jpeg')
    return [{'t_s': t, 'path': str(p)} for t in (0.4, 1.2, 2.0)]


def payload():
    return {'fires': [{'description': 'visible flame', 'location_description': 'left of rack',
                       'burning_object': None, 'smoke_description': None, 'nearby_objects': ['rack'],
                       'frame_boxes': [{'frame_index': 1, 'bbox_2d': [100, 200, 300, 500]},
                                       {'frame_index': 2, 'bbox_2d': [110, 210, 310, 510]}]}]}


class Response:
    status_code = 200
    def __init__(self, obj=None, status='completed', model='gpt-6-astra'):
        self.obj, self.status, self.model = obj, status, model
    def json(self):
        return {'status': self.status, 'model': self.model, 'output': [
            {'content': [{'type': 'output_text', 'text': json.dumps(self.obj)}]}]}


def install(monkeypatch, response):
    calls = []
    monkeypatch.setattr(grounding.config, 'get', lambda key: 'secret')
    def post(url, **kwargs):
        calls.append((url, kwargs))
        return response
    monkeypatch.setattr(grounding.requests, 'post', post)
    return calls


def test_valid_review_preserves_cosmos_and_marks_independent_boxes(monkeypatch, frames):
    calls = install(monkeypatch, Response(payload()))
    original = {'fire_sources': [{'id': 'F1', 'bbox_normalized': [0.8, 0.8, 0.9, 0.9]}],
                'scene_description': 'warehouse', 'unknowns': ['depth'], 'depth_m': None}
    before = copy.deepcopy(original)
    meta, corrected = grounding.review(frames, 2.4, original)
    assert original == before == meta['original_observations']
    assert corrected['scene_description'] == 'warehouse'
    f = corrected['fire_sources'][0]
    assert f['id'] == 'A1' and f['bbox_normalized'] == [0.11, 0.21, 0.31, 0.51]
    assert f['bbox_at_s'] == 1.2 and [b['t_s'] for b in f['bbox_by_frame']] == [0.4, 1.2]
    assert f['bbox_provenance']['model_id'] == 'gpt-6-astra'
    body = calls[0][1]['json']
    assert body['store'] is False and body['text']['format']['strict'] is True
    assert 'warehouse' not in json.dumps(body['input']) or 'warehouse' in grounding.PROMPT
    assert json.loads(meta['raw_text']) == payload()


@pytest.mark.parametrize('boxes', [
    [{'frame_index': 4, 'bbox_2d': [1,2,3,4]}],
    [{'frame_index': 1, 'bbox_2d': [1,2,3,4]}, {'frame_index': 1, 'bbox_2d': [1,2,3,4]}],
    [{'frame_index': 1, 'bbox_2d': [100,200,100,500]}],
    [{'frame_index': 1, 'bbox_2d': [-1,200,300,500]}],
    [{'frame_index': 1, 'bbox_2d': [1,2,float('nan'),4]}],
    [],
])
def test_invalid_boxes_fail_without_substitution(monkeypatch, frames, boxes):
    obj=payload(); obj['fires'][0]['frame_boxes']=boxes
    install(monkeypatch, Response(obj))
    with pytest.raises(grounding.InvalidGrounding):
        grounding.review(frames, 2.4, {'fire_sources': [{'id':'F1'}]})


def test_transport_and_incomplete_fail_closed(monkeypatch, frames):
    install(monkeypatch, Response(payload(), status='incomplete'))
    with pytest.raises(grounding.GroundingUnavailable):
        grounding.review(frames, 2.4, {})
    def fail(*args, **kwargs): raise requests.Timeout('private details')
    monkeypatch.setattr(grounding.requests, 'post', fail)
    with pytest.raises(grounding.GroundingUnavailable, match='Timeout') as exc:
        grounding.review(frames, 2.4, {})
    assert 'private details' not in str(exc.value)


def test_missing_key_and_wrong_model(monkeypatch, frames):
    monkeypatch.setattr(grounding.config, 'get', lambda key: None)
    with pytest.raises(grounding.GroundingUnavailable): grounding.review(frames, 2.4, {})
    install(monkeypatch, Response(payload(), model='other'))
    with pytest.raises(grounding.InvalidGrounding): grounding.review(frames, 2.4, {})


def test_failure_exposes_raw_and_original(monkeypatch, frames):
    obj = payload(); obj['fires'][0]['frame_boxes'][0]['bbox_2d'] = [1, 2, 1001, 4]
    install(monkeypatch, Response(obj))
    original = {'fire_sources': [{'id': 'F1'}]}
    with pytest.raises(grounding.InvalidGrounding) as caught:
        grounding.review(frames, 2.4, original)
    meta = caught.value.review_metadata
    assert meta['original_observations'] == original
    assert json.loads(meta['raw_text']) == obj
    assert meta['status'] == 'invalid' and meta['provider_status'] == 'completed'
    assert meta['model_id'] == 'gpt-6-astra' and meta['prompt_id'] == grounding.PROMPT_ID


@pytest.mark.parametrize('output', [None, {}, [None], ['invalid'], [{'content': None}],
                                     [{'content': {} }], [{'content': [None]}],
                                     [{'content': ['invalid']}], [{'content': [{'type': 'output_text'}]}]])
def test_malformed_response_envelope_preserves_evidence(monkeypatch, frames, output):
    class Malformed(Response):
        def json(self):
            return {'status': 'completed', 'model': 'gpt-6-astra', 'output': output,
                    'authorization': 'secret', 'message': 'secret'}
    install(monkeypatch, Malformed())
    with pytest.raises(grounding.InvalidGrounding) as caught:
        grounding.review(frames, 2.4, {'scene_description': 'original'})
    meta = caught.value.review_metadata
    assert meta['original_observations']['scene_description'] == 'original'
    assert meta['provider_response']['output'] == output
    assert meta['provider_response']['authorization'] == '[redacted]'
    assert meta['provider_response']['message'] == '[redacted]'


@pytest.mark.parametrize('model', [None, '', 'gpt-4'])
def test_absent_or_wrong_model_is_invalid(monkeypatch, frames, model):
    install(monkeypatch, Response(payload(), model=model))
    with pytest.raises(grounding.InvalidGrounding) as caught:
        grounding.review(frames, 2.4, {})
    assert caught.value.review_metadata['model_id'] == model


def test_duplicate_boxes_for_separate_fires_rejected_with_raw(monkeypatch, frames):
    obj = payload(); obj['fires'].append(copy.deepcopy(obj['fires'][0]))
    install(monkeypatch, Response(obj))
    with pytest.raises(grounding.InvalidGrounding, match='Near-identical') as caught:
        grounding.review(frames, 2.4, {})
    assert json.loads(caught.value.review_metadata['raw_text']) == obj


def test_missing_model_is_invalid(monkeypatch, frames):
    class MissingModel(Response):
        def json(self):
            return {'status': 'completed', 'output': []}
    install(monkeypatch, MissingModel())
    with pytest.raises(grounding.InvalidGrounding) as caught:
        grounding.review(frames, 2.4, {'fire_sources': []})
    assert caught.value.review_metadata['provider_response'] == {'status': 'completed', 'output': []}
