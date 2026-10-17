"""Scripted mobile warehouse response. Suppression is an exposure proxy, not fire physics."""
from __future__ import annotations

import copy
import math
import re
import xml.sax.saxutils as sax

import mujoco
import numpy as np

from .sim import TYPE_NAMES, TYPE_NDIM, _quat
from .robot_profile import ROBOT_PROFILE

TEMPLATE_ID = "wh_mobile_v1"
FPS = 30
HOLD_REQ_S = 2.0
MIN_RANGE_M, MAX_RANGE_M = 0.35, 3.5
THRESH_DEG = 5.0
STATION_POSE = [0.0, 0.0, 0.0]
# All locations are authored assumptions, not inferred metric coordinates.
SLOTS = {
    "left_rack": [[3.0, 1.45, 0.55], [4.5, 1.45, 0.55], [6.0, 1.45, 0.55]],
    "right_rack": [[3.0, -1.45, 0.55], [4.5, -1.45, 0.55], [6.0, -1.45, 0.55]],
    "aisle_center": [[3.0, 0.0, 0.45], [4.5, 0.0, 0.45], [6.0, 0.0, 0.45]],
    "loading_dock": [[7.5, 0.0, 0.55], [8.0, 0.75, 0.55], [8.0, -0.75, 0.55]],
}
RULE = "all targets receive >=2s continuous valid spray exposure and zero unintended collisions (scripted demo proxy)"


def target_position(zone, slot=0):
    if zone not in SLOTS or isinstance(slot, bool) or not isinstance(slot, int) or not 0 <= slot < len(SLOTS[zone]):
        raise ValueError(f"Unknown or unavailable warehouse slot {zone!r}/{slot!r}")
    return list(SLOTS[zone][slot])


def validate_settings(settings):
    expected = {"template_id", "route_profile", "walk_speed_m_s", "spray_profile", "spray_duration_s"}
    if not isinstance(settings, dict) or set(settings) != expected:
        raise ValueError("Invalid mobile scene settings")
    if (settings['template_id'] != TEMPLATE_ID or settings['route_profile'] != 'aisle_safe'
            or settings['spray_profile'] != 'water_demo'):
        raise ValueError("Unsupported mobile scene settings")
    for key, lo, hi in (("walk_speed_m_s", .25, 1.0), ("spray_duration_s", 3.0, 8.0)):
        v = settings[key]
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or not lo <= v <= hi:
            raise ValueError(f"{key} must be between {lo} and {hi}")
    return dict(settings)


def _fmt(values):
    return ' '.join(str(float(x)) for x in values)


def build_scene(confirmed_targets, settings):
    settings = validate_settings(settings)
    if not isinstance(confirmed_targets, list) or not 1 <= len(confirmed_targets) <= 12:
        raise ValueError("A mobile scene requires 1 to 12 confirmed targets")
    fires, mapping, placements = {}, {}, []
    slots = set()
    for target in confirmed_targets:
        fid = target.get('fire_id')
        if not isinstance(fid, str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*', fid) or fid in fires:
            raise ValueError("Each target needs a unique safe fire_id")
        zone, slot = target.get('zone'), target.get('slot', 0)
        pos = target_position(zone, slot)
        if (zone, slot) in slots:
            raise ValueError("Each target needs a distinct slot")
        if 'template_position_m' in target and target['template_position_m'] != pos:
            raise ValueError("Target position does not match its authored slot")
        slots.add((zone, slot))
        fires[fid] = {'pos': pos, 'zone': zone, 'slot': slot}
        mapping[fid] = {'zone': zone, 'slot': slot}
        placements.append({'name': 'fire_' + fid, 'pos': pos, 'provenance': 'operator-confirmed authored template slot'})
    # Aisle is clear of racks. Use physical obstacles with mutually compatible collision masks.
    env = ['<geom name="floor" type="plane" size="15 15 .1" rgba=".27 .3 .35 1" contype="1" conaffinity="2"/>',
           '<geom name="station" type="box" pos="-.35 0 .1" size=".34 .45 .1" rgba=".12 .65 .68 1" contype="0" conaffinity="0"/>']
    for side, y in (("L", 2.4), ("R", -2.4)):
        for i, x in enumerate((2., 4., 6., 8.)):
            env.append(f'<geom name="rack_{side}_{i}" type="box" pos="{x} {y} 1.2" size=".06 .18 1.2" rgba=".22 .33 .48 1" contype="1" conaffinity="2"/>')
        for i, z in enumerate((.45, 1.15, 1.9)):
            env.append(f'<geom name="shelf_{side}_{i}" type="box" pos="5 {y} {z}" size="3 .35 .045" rgba=".7 .43 .16 1" contype="1" conaffinity="2"/>')
    fire_xml = []
    for fid, fire in fires.items():
        x, y, z = fire['pos']
        fire_xml.append(f'<geom name="fire_{sax.escape(fid)}" type="capsule" fromto="{x} {y} {z} {x} {y} {z + .6}" size=".2" rgba="1 .25 .03 1" contype="0" conaffinity="0" group="3"/>')
        fire_xml.append(f'<geom name="fire_{sax.escape(fid)}_tip" type="capsule" fromto="{x} {y} {z + .25} {x + .08} {y} {z + .75}" size=".09" rgba="1 .7 .08 1" contype="0" conaffinity="0" group="3"/>')
    # +X is the nozzle direction; yaw and pitch are direct joints for reproducible kinematics.
    xml = f'''<mujoco model="wh_mobile_v1"><compiler angle="radian"/><option timestep="0.01"><flag filterparent="disable"/></option>
    <visual><global offwidth="1280" offheight="720"/></visual><worldbody>
    <light pos="4 0 8" dir="0 0 -1" diffuse=".8 .8 .8"/>
    <camera name="overview" pos="-6 0 6" xyaxes="0 -1 0 .4 0 .9165"/>
    {''.join(env)}{''.join(fire_xml)}
    <body name="robot_base" pos="0 0 0">
      <joint name="base_x" type="slide" axis="1 0 0"/><joint name="base_y" type="slide" axis="0 1 0"/>
      <geom name="robot_torso" type="box" pos="0 0 .83" size=".095 .10 .16" rgba=".95 .95 .95 1" group="1" contype="2" conaffinity="3"/>
      <geom name="robot_head" type="sphere" pos="0 0 1.13" size=".1" rgba=".95 .95 .95 1" group="1" contype="2" conaffinity="3"/>
      <geom name="robot_eye_l" type="sphere" pos=".091 .038 1.14" size=".016" rgba=".08 .1 .12 1" group="1" contype="0" conaffinity="0"/>
      <geom name="robot_eye_r" type="sphere" pos=".091 -.038 1.14" size=".016" rgba=".08 .1 .12 1" group="1" contype="0" conaffinity="0"/>
      <geom name="robot_left_upper_arm" type="capsule" fromto="0 .1485 .95 0 .1485 .75" size=".03" rgba=".7 .7 .7 1" group="1" contype="2" conaffinity="3"/>
      <geom name="robot_left_forearm" type="capsule" fromto="0 .1485 .73 .02 .1485 .53" size=".03" rgba=".95 .95 .95 1" group="1" contype="2" conaffinity="3"/>
      <body name="leg_left" pos="0 .075 .63"><joint name="leg_left_joint" axis="0 1 0"/>
       <geom name="robot_leg_l" type="capsule" fromto="0 0 0 0 0 -.29" size=".04" rgba=".95 .95 .95 1" group="1" contype="2" conaffinity="3"/>
       <geom name="robot_shin_l" type="capsule" fromto="0 0 -.31 0 0 -.59" size=".04" rgba=".7 .7 .7 1" group="1" contype="2" conaffinity="3"/></body>
      <body name="leg_right" pos="0 -.075 .63"><joint name="leg_right_joint" axis="0 1 0"/>
       <geom name="robot_leg_r" type="capsule" fromto="0 0 0 0 0 -.29" size=".04" rgba=".95 .95 .95 1" group="1" contype="2" conaffinity="3"/>
       <geom name="robot_shin_r" type="capsule" fromto="0 0 -.31 0 0 -.59" size=".04" rgba=".7 .7 .7 1" group="1" contype="2" conaffinity="3"/></body>
      <body name="arm_yaw" pos="0 -.145 .95"><inertial pos="0 0 0" mass=".1" diaginertia=".001 .001 .001"/><joint name="aim_yaw" axis="0 0 1"/>
       <body name="arm_pitch"><joint name="aim_pitch" axis="0 1 0"/>
        <geom name="robot_arm" type="capsule" fromto="0 0 0 .20 0 0" size=".03" rgba=".7 .7 .7 1" group="1" contype="2" conaffinity="3"/>
        <geom name="robot_forearm" type="capsule" fromto=".22 0 0 .42 0 0" size=".03" rgba=".95 .95 .95 1" group="1" contype="2" conaffinity="3"/>
        <geom name="ext_nozzle" type="cylinder" fromto=".42 0 0 .5 0 0" size=".025" rgba=".4 .4 .4 1" group="1" contype="2" conaffinity="3"/>
        <site name="nozzle" pos=".5 0 0" quat=".70710678 0 .70710678 0"/>
        <geom name="water_stream" type="cylinder" pos="1 0 0" quat=".70710678 0 .70710678 0" size=".055 .5" rgba=".25 .75 1 0" group="2" contype="0" conaffinity="0"/>
       </body></body></body></worldbody></mujoco>'''
    return {'template_id': TEMPLATE_ID, 'template_version': 2, 'mjcf': xml, 'fires': fires,
            'placements': placements, 'source_zone_mapping': mapping, 'settings': settings,
            'station_pose': list(STATION_POSE), 'target_ids': list(fires),
            'robot_profile': copy.deepcopy(ROBOT_PROFILE),
            'reference_kind': ROBOT_PROFILE['reference_kind'],
            'authored_proxy_dof': {'count': 6, 'base_translation': ['base_x', 'base_y'],
                                   'scripted_robot_joints': ['leg_left_joint', 'leg_right_joint', 'aim_yaw', 'aim_pitch']}}


def simulate(scene, skill):
    settings = validate_settings(scene.get('settings'))
    fires = scene.get('fires') or {}
    ids = skill.get('target_ids') if isinstance(skill, dict) else None
    if not isinstance(skill, dict) or skill.get('name') != 'mobile_suppress_demo' or not isinstance(ids, list) or len(ids) != len(fires) or len(set(ids)) != len(ids) or set(ids) != set(fires):
        raise ValueError('Skill must visit every confirmed target exactly once')
    model = mujoco.MjModel.from_xml_string(scene['mjcf'])
    data = mujoco.MjData(model)
    jid = {n: int(model.jnt_qposadr[mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, n)]) for n in ('base_x', 'base_y', 'leg_left_joint', 'leg_right_joint', 'aim_yaw', 'aim_pitch')}
    sid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_SITE, 'nozzle')
    names = [mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_GEOM, i) for i in range(model.ngeom)]
    def group(n):
        return 'fire' if n.startswith('fire_') else 'robot' if n.startswith('robot_') else 'extinguisher' if n.startswith('ext_') else 'env'
    geoms = []
    for i, name in enumerate(names):
        typ = TYPE_NAMES[int(model.geom_type[i])]
        geoms.append({'name': name, 'type': typ, 'size': [round(float(x), 4) for x in model.geom_size[i][:TYPE_NDIM[typ]]],
                      'rgba': [round(float(x), 3) for x in model.geom_rgba[i]], 'group': group(name)})
    frames, qposes, nozzle, angle_frames, phases, bases, spray = [], [], [], [], [], [], []
    pairset = set()
    reports = {fid: {'target_id': fid, 'visited': False, 'suppressed': False, 'min_angle_error_deg': None,
                     'min_distance_m': None, 'best_valid_exposure_s': 0., 'suppressed_at_s': None, 'failure_reason': None} for fid in ids}
    suppressed_frame = {fid: None for fid in ids}
    exposure = {fid: 0. for fid in ids}
    previous_valid = {fid: False for fid in ids}
    current_x = 0.0
    distance_total = 0.0
    frame_index = 0
    # Sample every frame and also subdivide each movement segment to <=2 cm for collision measurements.
    def sample(x, fid, phase, on, walking=False, record=True):
        nonlocal frame_index
        data.qpos[jid['base_x']] = x
        data.qpos[jid['base_y']] = 0
        leg = .32 * math.sin(x * 8.0) if walking else 0.
        data.qpos[jid['leg_left_joint']] = leg
        data.qpos[jid['leg_right_joint']] = -leg
        pos = np.asarray(fires[fid]['pos'], float)
        # Nozzle offset depends on yaw; refine analytically by repeated aim estimates.
        yaw = math.atan2(pos[1] + .145, pos[0] - x)
        for _ in range(5):
            pitch = 0.
            data.qpos[jid['aim_yaw']] = yaw
            data.qpos[jid['aim_pitch']] = pitch
            mujoco.mj_forward(model, data)
            rel = pos - data.site_xpos[sid]
            yaw += math.atan2(rel[1], rel[0]) - yaw
        data.qpos[jid['aim_yaw']] = yaw
        # Positive pitch rotates +X toward -Z; solve after yaw in world space.
        data.qpos[jid['aim_pitch']] = -math.atan2(pos[2] - .95, math.hypot(pos[0]-x, pos[1]+.145))
        # Travel/idle use a predefined forward carry pose. Aiming at a target behind
        # the robot during backward traversal swept the forearm through the torso.
        # Contact masks, checks and suppression rules are unchanged.
        if not on:
            data.qpos[jid['aim_yaw']] = 0.0
            data.qpos[jid['aim_pitch']] = 0.0
        mujoco.mj_forward(model, data)
        local_pairs = set()
        for c in data.contact:
            a, b = int(c.geom1), int(c.geom2)
            pair = frozenset((names[a], names[b]))
            robot_a = names[a].startswith(('robot_', 'ext_'))
            robot_b = names[b].startswith(('robot_', 'ext_'))
            expected = {
                frozenset(('floor', 'robot_shin_l')), frozenset(('floor', 'robot_shin_r')),
                frozenset(('robot_torso', 'robot_arm')),
                frozenset(('robot_torso', 'robot_leg_l')), frozenset(('robot_torso', 'robot_leg_r')),
            }
            if (robot_a or robot_b) and pair not in expected:
                local_pairs.add('|'.join(sorted((names[a], names[b]))))
        pairset.update(local_pairs)
        p = data.site_xpos[sid].copy()
        axis = data.site_xmat[sid].reshape(3, 3)[:, 2].copy()
        v = pos - p
        dist = float(np.linalg.norm(v))
        err = math.degrees(math.acos(float(np.clip(axis @ v / max(dist, 1e-12), -1, 1))))
        ray_groups = np.array([1, 0, 0, 0, 0, 0], dtype=np.uint8)
        hit = np.array([-1], dtype=np.int32)
        ray = mujoco.mj_ray(model, data, p, v / max(dist, 1e-12), ray_groups, True, -1, hit)
        clear = ray < 0 or ray >= dist - .01
        valid = on and MIN_RANGE_M <= dist <= MAX_RANGE_M and err <= THRESH_DEG and clear and not local_pairs
        if record:
            rep = reports[fid]
            if on:
                rep['visited'] = True
                rep['min_angle_error_deg'] = round(min(rep['min_angle_error_deg'] if rep['min_angle_error_deg'] is not None else err, err), 4)
                rep['min_distance_m'] = round(min(rep['min_distance_m'] if rep['min_distance_m'] is not None else dist, dist), 4)
                exposure[fid] = exposure[fid] + 1/FPS if valid and previous_valid[fid] else 0.
                previous_valid[fid] = valid
                rep['best_valid_exposure_s'] = round(max(rep['best_valid_exposure_s'], exposure[fid]), 4)
                if exposure[fid] + 1e-9 >= HOLD_REQ_S and not rep['suppressed']:
                    rep['suppressed'] = True
                    rep['suppressed_at_s'] = round(frame_index/FPS, 4)
                    suppressed_frame[fid] = frame_index
                if not valid:
                    rep['failure_reason'] = 'collision' if local_pairs else 'line of sight blocked' if not clear else 'outside spray range' if not MIN_RANGE_M <= dist <= MAX_RANGE_M else 'aim error exceeds threshold'
            row = []
            for gi in range(model.ngeom):
                row.extend(round(float(a), 5) for a in data.geom_xpos[gi]); row.extend(round(float(a), 5) for a in _quat(data.geom_xmat[gi]))
            frames.append(row); qposes.append([round(float(q), 7) for q in data.qpos]); nozzle.append([round(float(a), 5) for a in (*p, *axis)])
            angle_frames.append(round(err, 4)); phases.append(phase); bases.append([round(x, 5), 0., 0.])
            frame_index += 1
        return valid
    # first frame is charging station; move in the central aisle only.
    sample(0., ids[0], 'charging', False)
    for fid in ids:
        if pairset:
            for remaining in ids:
                if not reports[remaining]['suppressed']:
                    reports[remaining]['failure_reason'] = 'route blocked by collision'
            break
        goal_x = max(.25, float(fires[fid]['pos'][0]) - 1.5)
        delta = goal_x-current_x
        steps = max(1, math.ceil(abs(delta) / settings['walk_speed_m_s'] * FPS))
        previous = current_x
        blocked = False
        for j in range(1, steps+1):
            x = current_x + delta * j / steps
            subdivisions = max(1, math.ceil(abs(x-previous)/.02))
            for u in range(1, subdivisions + 1):
                sub_x = previous + (x-previous) * u/subdivisions
                before = len(pairset)
                sample(sub_x, fid, 'walking', False, True, u == subdivisions)
                if len(pairset) > before:
                    if u != subdivisions:
                        sample(sub_x, fid, 'collision', False, True)
                    distance_total += abs(sub_x-current_x)
                    current_x = sub_x
                    blocked = True
                    break
            if blocked:
                break
            previous = x
        if blocked:
            for remaining in ids:
                if not reports[remaining]['suppressed']:
                    reports[remaining]['failure_reason'] = 'route blocked by collision'
            break
        distance_total += abs(delta)
        current_x = goal_x
        spray.append({'frame': frame_index, 'on': True, 'target_id': fid})
        for _ in range(round(settings['spray_duration_s']*FPS)):
            sample(current_x, fid, 'spraying', True)
        spray.append({'frame': frame_index, 'on': False, 'target_id': fid})
        sample(current_x, fid, 'standing', False)
        if not reports[fid]['suppressed'] and not reports[fid]['failure_reason']:
            reports[fid]['failure_reason'] = 'insufficient continuous exposure'
        if reports[fid]['suppressed']:
            reports[fid]['failure_reason'] = None
    duration = (len(frames)-1)/FPS
    cols = sorted(pairset)
    target_reports = [reports[i] for i in ids]
    count = sum(r['suppressed'] for r in target_reports)
    valid_angles = [r['min_angle_error_deg'] for r in target_reports if r['min_angle_error_deg'] is not None]
    metrics = {'metric_version': 'mobile_exposure_v1', 'controller_version': 'r1_scripted_travel_pose_v2', 'target_count': len(ids), 'suppressed_count': count,
               'targets': target_reports, 'distance_travelled_m': round(distance_total, 4), 'started_at_charging_station': bases[0] == STATION_POSE,
               'angle_error_deg_final': angle_frames[-1], 'angle_error_deg_min': min(valid_angles) if valid_angles else None,
               'hold_s': min(r['best_valid_exposure_s'] for r in target_reports), 'duration_s': round(duration, 4),
               'unintended_collisions': cols, 'unintended_collision_count': len(cols), 'success': count == len(ids) and not cols, 'rule': RULE}
    traj = {'version': 'mobile_v1', 'fps': FPS, 'duration_s': round(duration, 4), 'geoms': geoms, 'frames': frames,
            'qpos': qposes, 'phases': phases, 'base_positions': bases, 'angle_error_deg': angle_frames,
            'fx': {'fires': [{'id': f, 'pos': fires[f]['pos'], 'target': True, 'suppressed_frame': suppressed_frame[f]} for f in fires],
                   'spray': spray, 'nozzle': nozzle}}
    return metrics, traj
