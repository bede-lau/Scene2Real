"""Warehouse template wh_aisle_v1: MJCF builder, zones, reachability."""
from __future__ import annotations

import math

TEMPLATE_ID = "wh_aisle_v1"
SHOULDER_POS = (0.0, -0.25, 1.4)  # world position of right shoulder (torso yaw = 0)
YAW_LIMIT_DEG = 100.0
MAX_REACH_M = 9.0
DEFAULT_SETTINGS = {"timestep": 0.002, "duration_s": 6.0}

ZONES: dict[str, dict] = {
    "left_rack": {"anchor": [4.0, 1.6, 0.5], "label": "Left pallet rack", "reachable": True},
    "right_rack": {"anchor": [4.0, -1.6, 0.5], "label": "Right pallet rack", "reachable": True},
    "aisle_center": {"anchor": [4.5, 0.0, 0.3], "label": "Aisle centre", "reachable": True},
    "loading_dock": {"anchor": [7.5, 0.0, 0.6], "label": "Loading dock", "reachable": True},
    "behind_robot": {"anchor": [-3.0, 0.0, 0.5], "label": "Behind robot", "reachable": False},
}

PROV_TEMPLATE = f"authored template {TEMPLATE_ID}"


def suggest_zone(bbox_normalized):
    """Suggest a zone from a normalised bbox (camera looks down the aisle). Suggestion only."""
    if not bbox_normalized or len(bbox_normalized) != 4:
        return None
    cx = (float(bbox_normalized[0]) + float(bbox_normalized[2])) / 2.0
    if cx < 0.4:
        return "left_rack"
    if cx > 0.6:
        return "right_rack"
    return "aisle_center"


def _f(v):
    return " ".join(f"{x:.4f}".rstrip("0").rstrip(".") if abs(x) > 1e-12 else "0" for x in v)


def _env_geoms(placements: list) -> str:
    """Static environment: floor, 2 rack rows, pallets with boxes."""
    g = ['<geom name="floor" type="plane" size="20 20 0.1" rgba="0.55 0.55 0.58 1" contype="1" conaffinity="2"/>']
    col = 'contype="1" conaffinity="2"'
    post_xs = [2.0, 3.25, 4.5, 5.75, 7.0]
    shelf_zs = [0.4, 1.2, 2.0]
    for side, yc, tag in ((1, 2.0, "L"), (-1, -2.0, "R")):
        for i, x in enumerate(post_xs):
            for j, dy in enumerate((-0.3, 0.3)):
                g.append(f'<geom name="rack_{tag}_post{i}_{j}" type="box" pos="{_f([x, yc + dy, 1.2])}" '
                         f'size="0.04 0.04 1.2" rgba="0.15 0.3 0.7 1" {col}/>')
        for k, z in enumerate(shelf_zs):
            g.append(f'<geom name="rack_{tag}_shelf{k}" type="box" pos="{_f([4.5, yc, z])}" '
                     f'size="2.5 0.3 0.02" rgba="0.9 0.5 0.1 1" {col}/>')
            for b, bx in enumerate((2.9, 4.5, 6.1)):
                if k == 0 and b == 1:
                    continue
                g.append(f'<geom name="box_{tag}_s{k}_{b}" type="box" pos="{_f([bx, yc, z + 0.02 + 0.2])}" '
                         f'size="0.4 0.25 0.2" rgba="0.7 0.55 0.35 1" {col}/>')
        placements.append({"name": f"rack_row_{tag}", "pos": [4.5, yc, 0.0],
                           "provenance": PROV_TEMPLATE})
    for p, (px, py) in enumerate(((3.0, 1.55), (5.5, 1.55), (3.0, -1.55), (5.5, -1.55))):
        g.append(f'<geom name="pallet_{p}" type="box" pos="{_f([px, py, 0.075])}" size="0.5 0.35 0.075" '
                 f'rgba="0.6 0.45 0.25 1" {col}/>')
        g.append(f'<geom name="box_pallet_{p}" type="box" pos="{_f([px, py, 0.15 + 0.1])}" size="0.35 0.25 0.1" '
                 f'rgba="0.75 0.6 0.4 1" {col}/>')
        placements.append({"name": f"pallet_{p}", "pos": [px, py, 0.075], "provenance": PROV_TEMPLATE})
    return "\n    ".join(g)


_ROBOT = """
    <body name="robot_legs">
      <geom name="robot_leg_l" type="capsule" fromto="0 0.1 0.07 0 0.1 0.85" size="0.07" rgba="0.2 0.2 0.25 1" contype="2" conaffinity="3"/>
      <geom name="robot_leg_r" type="capsule" fromto="0 -0.1 0.07 0 -0.1 0.85" size="0.07" rgba="0.2 0.2 0.25 1" contype="2" conaffinity="3"/>
    </body>
    <body name="robot_torso" pos="0 0 1.0" gravcomp="1">
      <joint name="torso_yaw" type="hinge" axis="0 0 1" range="-1.745 1.745" damping="60" armature="0.05"/>
      <geom name="robot_torso" type="box" pos="0 0 0.25" size="0.12 0.18 0.28" rgba="0.85 0.85 0.9 1" contype="2" conaffinity="3"/>
      <geom name="robot_head" type="sphere" pos="0 0 0.68" size="0.12" rgba="0.9 0.8 0.7 1" contype="2" conaffinity="3"/>
      <geom name="robot_larm_upper" type="capsule" fromto="0 0.25 0.4 0 0.25 0.1" size="0.04" rgba="0.85 0.85 0.9 1" contype="2" conaffinity="3"/>
      <geom name="robot_larm_fore" type="capsule" fromto="0 0.25 0.1 0.05 0.25 -0.15" size="0.035" rgba="0.85 0.85 0.9 1" contype="2" conaffinity="3"/>
      <body name="robot_sh_yaw" pos="0 -0.25 0.4" gravcomp="1">
        <inertial pos="0 0 0" mass="0.1" diaginertia="0.001 0.001 0.001"/>
        <joint name="shoulder_yaw" type="hinge" axis="0 0 1" range="-1.5 1.5" damping="60" armature="0.05"/>
        <body name="robot_uarm" gravcomp="1">
          <inertial pos="0 0 -0.15" mass="1.0" diaginertia="0.01 0.01 0.002"/>
          <joint name="shoulder_pitch" type="hinge" axis="0 1 0" range="-3.0 0.5" damping="60" armature="0.05"/>
          <geom name="robot_rarm_upper" type="capsule" fromto="0 0 0 0 0 -0.3" size="0.04" rgba="0.85 0.85 0.9 1" contype="2" conaffinity="3"/>
          <body name="robot_fore" pos="0 0 -0.3" gravcomp="1">
            <joint name="elbow" type="hinge" axis="0 1 0" range="-2.2 0.1" damping="60" armature="0.05"/>
            <geom name="robot_rarm_fore" type="capsule" fromto="0 0 0 0 0 -0.3" size="0.035" rgba="0.85 0.85 0.9 1" contype="2" conaffinity="3"/>
            <body name="robot_hand" pos="0 0 -0.3" gravcomp="1">
              <geom name="robot_hand" type="sphere" size="0.05" rgba="0.9 0.8 0.7 1" contype="2" conaffinity="3"/>
              <body name="ext_body" pos="0 0 -0.05" gravcomp="1">
                <geom name="ext_cylinder" type="cylinder" fromto="0 0 -0.02 0 0 -0.4" size="0.05" rgba="0.85 0.1 0.1 1" contype="2" conaffinity="3"/>
                <geom name="ext_nozzle" type="cylinder" fromto="0 0 -0.4 0 0 -0.55" size="0.015" rgba="0.1 0.1 0.1 1" contype="2" conaffinity="3"/>
                <site name="nozzle" pos="0 0 -0.55" quat="0 1 0 0" size="0.01"/>
              </body>
            </body>
          </body>
        </body>
      </body>
    </body>"""

_ACTUATORS = """
  <contact>
    <exclude body1="robot_torso" body2="robot_uarm"/>
    <exclude body1="robot_torso" body2="robot_legs"/>
  </contact>
  <actuator>
    <position name="a_torso_yaw" joint="torso_yaw" kp="600" ctrlrange="-1.745 1.745"/>
    <position name="a_shoulder_yaw" joint="shoulder_yaw" kp="600" ctrlrange="-1.5 1.5"/>
    <position name="a_shoulder_pitch" joint="shoulder_pitch" kp="600" ctrlrange="-3.0 0.5"/>
    <position name="a_elbow" joint="elbow" kp="600" ctrlrange="-2.2 0.1"/>
  </actuator>"""


def build_scene(fire_sources: list, mapping: dict, target_id: str) -> dict:
    ids = {f["id"] for f in fire_sources}
    for fid, zone in mapping.items():
        if zone not in ZONES:
            raise ValueError(f"unknown zone '{zone}' for fire '{fid}'")
        if fid not in ids:
            raise ValueError(f"mapped fire '{fid}' is not a detected fire source")
    if target_id not in mapping:
        raise ValueError(f"target '{target_id}' is not mapped to a zone")
    settings = dict(DEFAULT_SETTINGS)
    placements: list = []
    env = _env_geoms(placements)
    placements.append({"name": "robot", "pos": [0.0, 0.0, 0.0], "provenance": PROV_TEMPLATE})
    fires_xml, fires = [], {}
    for fid, zone in mapping.items():
        pos = list(ZONES[zone]["anchor"])
        fires[fid] = {"zone": zone, "pos": pos}
        rgba = "1 0.35 0.05 0.85" if fid == target_id else "1 0.6 0.1 0.6"
        fires_xml.append(f'<geom name="fire_{fid}" type="sphere" pos="{_f(pos)}" size="0.22" rgba="{rgba}" '
                         f'contype="0" conaffinity="0" group="3"/>')
        placements.append({"name": f"fire_{fid}", "pos": pos,
                           "provenance": f"zone anchor {zone}, confirmed by user"})
    mjcf = (f'<mujoco model="{TEMPLATE_ID}">\n'
            f'  <compiler angle="radian"/>\n'
            f'  <option timestep="{settings["timestep"]}" gravity="0 0 -9.81"/>\n'
            f'  <worldbody>\n    {env}\n    {chr(10).join(fires_xml)}\n{_ROBOT}\n  </worldbody>{_ACTUATORS}\n</mujoco>')
    return {"template_id": TEMPLATE_ID, "mjcf": mjcf,
            "source_zone_mapping": dict(mapping), "placements": placements,
            "target_id": target_id, "target_pos": fires[target_id]["pos"],
            "fires": fires, "settings": settings}


def check_reachable(scene: dict, target_id: str) -> tuple[bool, str]:
    fires = scene.get("fires") or {}
    if target_id not in fires:
        return False, f"target '{target_id}' is not mapped to a zone in this scene"
    x, y, z = fires[target_id]["pos"]
    zone = fires[target_id].get("zone", "?")
    yaw = math.degrees(math.atan2(y, x))
    if abs(yaw) > YAW_LIMIT_DEG:
        return False, (f"zone '{zone}' is at {yaw:.0f} deg from the robot's forward axis; "
                       f"torso yaw limit is +/-{YAW_LIMIT_DEG:.0f} deg")
    dist = math.dist((x, y, z), SHOULDER_POS)
    if dist > MAX_REACH_M:
        return False, f"zone '{zone}' is {dist:.1f} m away; max aiming distance is {MAX_REACH_M:.0f} m"
    return True, f"zone '{zone}' reachable (yaw {yaw:.0f} deg, distance {dist:.1f} m)"
