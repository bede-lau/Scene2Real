import copy

import pytest

from scene2real import mobile

SETTINGS = {'template_id': 'wh_mobile_v1', 'route_profile': 'aisle_safe', 'walk_speed_m_s': 1.0,
            'spray_profile': 'water_demo', 'spray_duration_s': 3.0}
TARGETS = [{'fire_id': 'T1', 'zone': 'left_rack', 'slot': 0},
           {'fire_id': 'T2', 'zone': 'right_rack', 'slot': 1},
           {'fire_id': 'T3', 'zone': 'aisle_center', 'slot': 2},
           {'fire_id': 'T4', 'zone': 'loading_dock', 'slot': 0}]


def make(n=1):
    targets = copy.deepcopy(TARGETS[:n])
    scene = mobile.build_scene(targets, SETTINGS)
    return scene, {'name': 'mobile_suppress_demo', 'target_ids': [t['fire_id'] for t in targets]}


@pytest.mark.parametrize('n', [1, 2, 3, 4])
def test_deterministic_scripted_routes_and_all_target_exposure(n):
    scene, skill = make(n)
    metrics, traj = mobile.simulate(scene, skill)
    again, again_traj = mobile.simulate(scene, skill)
    assert metrics == again and traj == again_traj
    assert metrics['success'] and metrics['suppressed_count'] == n
    assert metrics['started_at_charging_station'] and metrics['distance_travelled_m'] > 0
    assert all(t['best_valid_exposure_s'] >= 2 and t['suppressed_at_s'] is not None for t in metrics['targets'])
    assert len(set(tuple(q[2:4]) for q, p in zip(traj['qpos'], traj['phases']) if p == 'walking')) > 3
    assert [e['target_id'] for e in traj['fx']['spray'] if e['on']] == skill['target_ids']
    assert all(f['suppressed_frame'] is not None for f in traj['fx']['fires'])


def test_invalid_plan_and_duplicate_slot_rejected():
    scene, skill = make(2)
    with pytest.raises(ValueError):
        mobile.simulate(scene, {'name': skill['name'], 'target_ids': ['T1', 'T1']})
    with pytest.raises(ValueError):
        mobile.build_scene([TARGETS[0], dict(TARGETS[0], fire_id='T2')], SETTINGS)
    with pytest.raises(ValueError):
        mobile.validate_settings(dict(SETTINGS, walk_speed_m_s=float('nan')))
    with pytest.raises(ValueError):
        mobile.target_position('behind_robot', 0)


def test_contact_on_route_causes_failure():
    scene, skill = make()
    obstacle = '<geom name="blocker" type="box" pos=".8 0 1.1" size=".15 .4 .5" contype="1" conaffinity="2"/>'
    scene['mjcf'] = scene['mjcf'].replace('<body name="robot_base"', obstacle + '<body name="robot_base"')
    metrics, _ = mobile.simulate(scene, skill)
    assert not metrics['success']
    assert metrics['unintended_collision_count'] > 0
    assert any('blocker' in c for c in metrics['unintended_collisions'])


def test_obstructed_line_of_sight_cannot_suppress():
    scene, skill = make()
    # Between the stopped nozzle and left-rack target, but beyond robot reach.
    obstacle = '<geom name="screen" type="box" pos="2.5 .85 .9" size=".15 .25 .7" contype="1" conaffinity="2"/>'
    scene['mjcf'] = scene['mjcf'].replace('<body name="robot_base"', obstacle + '<body name="robot_base"')
    metrics, _ = mobile.simulate(scene, skill)
    assert not metrics['success']
    assert not metrics['targets'][0]['suppressed']
    assert metrics['targets'][0]['failure_reason'] == 'line of sight blocked'


def test_insufficient_exposure_cannot_suppress(monkeypatch):
    scene, skill = make()
    monkeypatch.setattr(mobile, 'HOLD_REQ_S', 4.0)
    metrics, _ = mobile.simulate(scene, skill)
    assert not metrics['success']
    assert metrics['targets'][0]['failure_reason'] == 'insufficient continuous exposure'


def test_torso_on_floor_is_not_an_allowed_floor_contact():
    scene, skill = make()
    scene['mjcf'] = scene['mjcf'].replace('name="robot_torso" type="box" pos="0 0 .83"',
                                          'name="robot_torso" type="box" pos="0 0 .05"')
    metrics, trajectory = mobile.simulate(scene, skill)
    assert not metrics['success']
    assert 'floor|robot_torso' in metrics['unintended_collisions']
    assert metrics['distance_travelled_m'] == 0
    assert not any(event['on'] for event in trajectory['fx']['spray'])


def test_nonadjacent_robot_leg_overlap_is_reported():
    scene, skill = make()
    scene['mjcf'] = scene['mjcf'].replace('name="leg_left" pos="0 .075 .63"',
                                          'name="leg_left" pos="0 -.075 .63"')
    metrics, trajectory = mobile.simulate(scene, skill)
    assert not metrics['success']
    assert 'robot_leg_l|robot_leg_r' in metrics['unintended_collisions']
    assert metrics['distance_travelled_m'] == 0
    assert not any(event['on'] for event in trajectory['fx']['spray'])


def test_r1_proxy_reference_and_proportions_are_explicit():
    import mujoco
    from scene2real.robot_profile import ROBOT_PROFILE

    scene, _ = make()
    assert scene['template_version'] == 2
    assert scene['robot_profile']['name'] == ROBOT_PROFILE['name'] == 'Unitree R1'
    assert 'approximation' in scene['reference_kind']
    assert scene['authored_proxy_dof']['count'] == 6
    assert len(scene['authored_proxy_dof']['scripted_robot_joints']) == 4
    model = mujoco.MjModel.from_xml_string(scene['mjcf'])
    data = mujoco.MjData(model)
    mujoco.mj_forward(model, data)
    def geom(name):
        return mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, name)
    assert model.nq == 6
    head = geom('robot_head')
    assert data.geom_xpos[head, 2] + model.geom_size[head, 0] == pytest.approx(1.23)
    assert geom('robot_eye_l') >= 0 and geom('robot_eye_r') >= 0
    assert geom('robot_left_upper_arm') >= 0 and geom('robot_forearm') >= 0
    assert geom('robot_shin_l') >= 0 and geom('robot_shin_r') >= 0
    assert data.geom_xpos[geom('robot_shin_l'), 2] - model.geom_size[geom('robot_shin_l'), 1] - model.geom_size[geom('robot_shin_l'), 0] == pytest.approx(0, abs=1e-6)


@pytest.mark.parametrize('speed',[.25,.6,1.0])
def test_backward_travel_uses_carry_pose_without_ignoring_contacts(speed):
    targets=[{'fire_id':'T1','zone':'loading_dock','slot':0},
             {'fire_id':'T2','zone':'left_rack','slot':0},
             {'fire_id':'T3','zone':'right_rack','slot':1}]
    scene=mobile.build_scene(targets,dict(SETTINGS,walk_speed_m_s=speed))
    metrics,traj=mobile.simulate(scene,{'name':'mobile_suppress_demo','target_ids':['T1','T2','T3']})
    assert metrics['success'] and metrics['unintended_collisions']==[]
    assert all(q[4:]==[0.,0.] for q,phase in zip(traj['qpos'],traj['phases']) if phase=='walking')
    assert all(t['best_valid_exposure_s']>=2 for t in metrics['targets'])
