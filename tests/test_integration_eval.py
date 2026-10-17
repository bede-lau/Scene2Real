"""Evaluation invariants, independent of paid inference."""
import hashlib
import json
from pathlib import Path

from evals.scorers import acceptance, mobile_score, replay_exposure
from scene2real import mobile


def test_locked_dataset_digest_and_disjoint_families():
    root = Path(__file__).parents[1] / 'evals/datasets'
    data = (root / 'integration_v1.json').read_bytes()
    manifest = json.loads((root / 'integration_v1.manifest.json').read_text())
    assert hashlib.sha256(data).hexdigest() == manifest['dataset_sha256']
    rows = json.loads(data)
    dev = {r['family'] for r in rows if r['split'] == 'development'}
    test = {r['family'] for r in rows if r['split'] == 'locked_test'}
    assert len(dev) == 4 and len(test) == 8 and not dev & test
    assert all('expected' not in r['case'] for r in rows)


def test_mobile_score_does_not_trust_success_flag():
    metrics = {'success': True, 'targets': [{'best_valid_exposure_s': 1.9, 'suppressed_at_s': 2}],
               'unintended_collision_count': 0}
    assert not mobile_score(metrics)['simulation_success']
    assert not mobile_score(metrics)['measurement_consistent']
    metrics['targets'][0]['best_valid_exposure_s'] = float('nan')
    assert not mobile_score(metrics)['simulation_success']


def test_replay_independently_recovers_continuous_exposure():
    targets = [{'fire_id': 'T1', 'zone': 'left_rack', 'slot': 1}]
    settings = {'template_id':'wh_mobile_v1','route_profile':'aisle_safe','walk_speed_m_s':1.,
                'spray_profile':'water_demo','spray_duration_s':3.}
    scene = mobile.build_scene(targets, settings)
    metrics, trajectory = mobile.simulate(scene, {'name':'mobile_suppress_demo','target_ids':['T1']})
    audit = replay_exposure(scene, trajectory, metrics)
    assert audit['replay_exposure_consistent']
    assert audit['audited_continuous_exposure_s']['T1'] >= 2


def test_gate_rejects_missing_baseline_and_any_collision():
    rows = [{'case_id':f'case_{i//2}', 'split':'locked_test','provider':'wandb','valid':True,'simulation_success':True,
             'collision_count':0} for i in range(16)]
    assert not acceptance(rows, False)['eligible_for_review']
    assert acceptance(rows, True)['eligible_for_review']
    rows[-1]['collision_count'] = 1
    assert not acceptance(rows, True)['eligible_for_review']
    assert not acceptance(rows, True)['candidate_promoted']
    assert not acceptance(rows[:1], True)['eligible_for_review']


def test_exact_timestamp_perception_scoring_does_not_use_nearest():
    from evals.perception import exact_sources
    sources=[{'id':'F1','bbox_by_frame':[{'t_s':2.4,'bbox_normalized':[.1,.1,.2,.2]}]}]
    assert exact_sources(sources,2.5)[0]['bbox_by_frame'][0]['bbox_normalized'] is None
    assert exact_sources([{'id':'F1','bbox_normalized':[.1,.1,.2,.2]}],2.5)[0]['bbox_normalized'] is None
