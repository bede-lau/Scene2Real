"""Pinned Menagerie G1, fixed-base dynamics and browser mesh conversion.

The original SI geometry, link inertias, hierarchy, axes, ranges and actuator force
limits are retained. Changes: fixed pelvis, finite-gain servos, wrist tool and a
warehouse. Presets are deterministic authored IK references, never a learned policy.
"""
from __future__ import annotations

from functools import lru_cache
import hashlib
import json
from pathlib import Path
import shutil
import xml.etree.ElementTree as ET

import mujoco
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
ASSET_DIR = ROOT / "assets" / "unitree_g1"
BROWSER_DIR = ROOT / "static" / "assets" / "unitree_g1"
COMMIT = "62ab00f2bc44f6f20c1c9b7a13f3fb1dd41a4e35"
SOURCE = f"https://github.com/google-deepmind/mujoco_menagerie/tree/{COMMIT}/unitree_g1"
MODEL_ID = f"menagerie-g1-{COMMIT[:12]}-fixed-wrist-v1"
TARGETS = {"left": [2.5, 0.8, 0.9], "center": [2.7, 0.0, 0.9], "right": [2.5, -0.8, 0.9]}
ARM_JOINTS = ["right_" + n + "_joint" for n in (
    "shoulder_pitch", "shoulder_roll", "shoulder_yaw", "elbow", "wrist_roll", "wrist_pitch", "wrist_yaw")]


@lru_cache(maxsize=1)
def simulation_identity() -> dict:
    """Identify actual local input assets and the authored control contract."""
    hashes = {str(path.relative_to(ASSET_DIR)): hashlib.sha256(path.read_bytes()).hexdigest()
              for path in sorted(ASSET_DIR.rglob("*")) if path.is_file()}
    return {"mode": "live_g1_fixed_base", "model_id": MODEL_ID,
            "source_commit": COMMIT, "source": SOURCE,
            "source_asset_sha256": hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest(),
            "authored_model_sha256": hashlib.sha256(_xml().replace(str(ASSET_DIR), "ASSET_DIR").encode()).hexdigest(),
            "capabilities": {"fixed_base": True, "walking": False, "max_targets": 1,
                             "poses": ["rest", "left", "center", "right"],
                             "placement": "exact authored G1 anchor", "physics_owner": "server MuJoCo",
                             "suppression": "unobstructed nozzle-ray intensity reduction, 0.24 per simulated second"}}


def _add(parent, tag, **attrs):
    return ET.SubElement(parent, tag, {k: str(v) for k, v in attrs.items()})


def _xml() -> str:
    root = ET.parse(ASSET_DIR / "g1.xml").getroot()
    root.set("model", MODEL_ID)
    root.find("compiler").set("meshdir", str(ASSET_DIR / "assets"))
    root.find("option").set("timestep", "0.002")
    root.find("option").set("gravity", "0 0 -9.81")
    # Original geometry and inertial parameters are unchanged. Fixing the pelvis
    # is an explicit fixture, rather than pretending to have a balance policy.
    pelvis = root.find(".//body[@name='pelvis']")
    pelvis.remove(pelvis.find("freejoint"))
    pelvis.set("pos", "0 0 0.793")
    root.find("default/default/default[@class='collision']/geom").set("group", "1")
    root.find("keyframe/key").set("qpos", " ".join(root.find("keyframe/key").get("qpos").split()[7:]))
    for actuator in root.findall("actuator/position"):
        name = actuator.get("joint")
        joint = root.find(f".//joint[@name='{name}']")
        actuator.set("forcelimited", "true")
        actuator.set("forcerange", joint.get("actuatorfrcrange"))
        # Conservative finite servos, not calibrated physical motor parameters.
        kp = 250 if "shoulder" in name or "elbow" in name else 100 if "wrist" in name else 350
        actuator.set("kp", str(kp))
        actuator.set("dampratio", "1")
    world = root.find("worldbody")
    _add(root, "visual")
    visual = root.find("visual")
    _add(visual, "global", offwidth="1280", offheight="960")
    _add(visual, "headlight", ambient="0.45 0.45 0.48", diffuse="0.65 0.65 0.62", specular="0.2 0.2 0.2")
    _add(visual, "map", znear="0.01", zfar="40", shadowscale="0.7")
    _add(world, "geom", name="live_floor", type="plane", size="10 10 0.1", rgba="0.22 0.26 0.29 1", group="0", friction="0.8 0.02 0.002")
    _add(world, "light", name="live_key", pos="1 -3 5", dir="0 0 -1", diffuse="0.8 0.85 0.9", castshadow="true")
    _add(world, "light", name="live_fill", pos="3 3 4", dir="0 0 -1", diffuse="0.5 0.55 0.65", castshadow="false")
    # Warehouse structure is collidable and is included in nozzle ray queries.
    _add(world, "geom", name="live_back_wall", type="box", pos="7 0 1.6", size="0.1 5 1.6", rgba="0.37 0.43 0.48 1", group="0")
    for y in (-2.3, 2.3):
        side = "south" if y < 0 else "north"
        for x in (1.5, 3.4):
            for yy in (y - .32, y + .32):
                _add(world, "geom", name=f"live_rack_{side}_{x}_{yy}", type="box", pos=f"{x} {yy} 1.1", size="0.035 0.035 1.1", rgba="0.13 0.25 0.31 1", group="0")
        for z in (.25, 1.1, 2.1):
            _add(world, "geom", name=f"live_shelf_{side}_{z}", type="box", pos=f"2.45 {y} {z}", size="1.0 .36 .035", rgba="0.2 0.33 0.38 1", group="0")
        for x in (1.9, 2.6, 3.1):
            _add(world, "geom", name=f"live_crate_{side}_{x}", type="box", pos=f"{x} {y} .49", size=".22 .26 .20", rgba="0.46 0.38 0.26 1", group="0")
    for name, pos in TARGETS.items():
        _add(world, "geom", name=f"live_pad_{name}", type="cylinder", pos=f"{pos[0]} {pos[1]} .015", size=".4 .015", rgba="0.28 0.39 0.42 1", group="0")
        # The flame proxy starts at z=.58; a physical burner pedestal grounds
        # the rendered flames and participates in the same world ray queries.
        _add(world, "geom", name=f"live_burner_{name}", type="box", pos=f"{pos[0]} {pos[1]} .28", size=".24 .24 .28", rgba=".23 .28 .30 1", group="0")
        _add(world, "geom", name=f"live_burner_rim_{name}", type="box", pos=f"{pos[0]} {pos[1]} .57", size=".27 .27 .01", rgba=".13 .17 .19 1", group="0")
    fire = _add(world, "body", name="live_fire_body", mocap="true", pos="2.7 0 .9")
    # MuJoCo rays skip fully transparent geoms, so retain a nonzero alpha here;
    # the frontend hides this proxy and renders its own animated fire.
    _add(fire, "geom", name="live_fire", type="sphere", size=".32", rgba="1 .20 .015 .01", group="3", contype="0", conaffinity="0")
    blocker = _add(world, "body", name="live_occluder_body", mocap="true", pos="1.35 4 .85")
    _add(blocker, "geom", name="live_occluder", type="box", size=".10 1.10 .85", rgba=".20 .25 .28 1", group="0")
    torso = root.find(".//body[@name='torso_link']")
    _add(torso, "camera", name="live_camera", pos=".075 0 .42", xyaxes="0 -1 0 .13 0 .991514", fovy="64")
    wrist = root.find(".//body[@name='right_wrist_yaw_link']")
    tool = _add(wrist, "body", name="live_extinguisher", pos=".09 -.005 -.025")
    _add(tool, "inertial", mass=".55", pos="0 0 -.10", diaginertia=".004 .004 .0012")
    _add(tool, "geom", name="live_extinguisher_tank", type="cylinder", pos="0 0 -.10", size=".047 .12", rgba=".72 .035 .025 1", group="2")
    _add(tool, "geom", name="live_extinguisher_band", type="cylinder", pos="0 0 -.10", size=".048 .032", rgba=".87 .91 .92 1", group="2", contype="0", conaffinity="0", mass="0")
    _add(tool, "geom", name="live_extinguisher_nozzle", type="cylinder", pos=".055 0 .025", quat=".70710678 0 .70710678 0", size=".017 .065", rgba=".08 .10 .12 1", group="2", mass="0")
    _add(tool, "site", name="live_nozzle", pos=".125 0 .025", quat=".70710678 0 .70710678 0", size=".01", rgba=".2 .8 1 1")
    return ET.tostring(root, encoding="unicode")


@lru_cache(maxsize=1)
def get_model() -> mujoco.MjModel:
    if not (ASSET_DIR / "g1.xml").exists():
        raise RuntimeError("G1 assets missing; run .venv/bin/python scripts/fetch_g1_assets.py")
    return mujoco.MjModel.from_xml_string(_xml())


def create_data(model: mujoco.MjModel) -> mujoco.MjData:
    data = mujoco.MjData(model)
    mujoco.mj_resetDataKeyframe(model, data, 0)
    mujoco.mj_forward(model, data)
    return data


def home_pose(model: mujoco.MjModel) -> dict[str, float]:
    return {model.joint(i).name: float(model.key_qpos[0, model.jnt_qposadr[i]]) for i in range(model.njnt)}


@lru_cache(maxsize=2)
def build_presets(model: mujoco.MjModel) -> dict[str, dict[str, float]]:
    """Author three fixed references once, using damped finite-difference IK.

    This is an offline pose authoring step. Live execution tracks the fixed
    references through bounded actuators; qpos is never teleported at runtime.
    """
    data = create_data(model)
    sid = model.site("live_nozzle").id
    names = ["waist_yaw_joint", *ARM_JOINTS]
    jids = [model.joint(n).id for n in names]
    adrs = model.jnt_qposadr[jids]
    limits = model.jnt_range[jids]
    reference = np.array([0, -1.05, -.10, 0, .9, 0, -.25, 0.0])
    out = {"rest": home_pose(model)}
    for label, target in TARGETS.items():
        target = np.asarray(target, dtype=float)
        seed = reference.copy()
        seed[0] = np.arctan2(target[1], target[0]) * .45

        def residual(q):
            data.qpos[adrs] = q
            mujoco.mj_forward(model, data)
            direction = target - data.site_xpos[sid]
            direction /= np.linalg.norm(direction)
            axis = data.site_xmat[sid].reshape(3, 3)[:, 2]
            # Keep wrist extended in front of body, elbow bent and posture close
            # to authored seed while solving the ray heading to high precision.
            hand = data.site_xpos[sid]
            return np.concatenate([axis - direction, .008 * (q - seed), [.02 * max(.35 - hand[0], 0)]])

        q = seed.copy()
        damping = 1e-4
        for _ in range(100):
            r = residual(q)
            jac = np.column_stack([(residual(q + np.eye(len(q))[k] * 1e-5) - r) / 1e-5 for k in range(len(q))])
            step = -np.linalg.solve(jac.T @ jac + damping * np.eye(len(q)), jac.T @ r)
            trial = np.clip(q + np.clip(step, -.15, .15), limits[:, 0] + .02, limits[:, 1] - .02)
            if np.linalg.norm(residual(trial)) < np.linalg.norm(r):
                q = trial
                damping = max(damping * .7, 1e-7)
            else:
                damping *= 3
        pose = home_pose(model)
        pose.update({n: float(v) for n, v in zip(names, q)})
        out[label] = pose
    return out


def manifest(model: mujoco.MjModel) -> dict:
    """Export compiled vertices, already in each compiled geom's local frame."""
    BROWSER_DIR.mkdir(parents=True, exist_ok=True)
    for filename in ("LICENSE", "SOURCE.json"):
        shutil.copyfile(ASSET_DIR / filename, BROWSER_DIR / filename)
    for mesh_id in range(model.nmesh):
        path = BROWSER_DIR / f"mesh_{mesh_id}.json"
        if not path.exists():
            va, vn = int(model.mesh_vertadr[mesh_id]), int(model.mesh_vertnum[mesh_id])
            fa, fn = int(model.mesh_faceadr[mesh_id]), int(model.mesh_facenum[mesh_id])
            payload = {"vertices": np.round(model.mesh_vert[va:va + vn].reshape(-1), 7).tolist(),
                       "indices": model.mesh_face[fa:fa + fn].reshape(-1).tolist()}
            path.write_text(json.dumps(payload, separators=(",", ":")))
    types = {int(getattr(mujoco.mjtGeom, "mjGEOM_" + n.upper())): n for n in ("plane", "sphere", "capsule", "ellipsoid", "cylinder", "box", "mesh")}
    geoms = []
    for i in range(model.ngeom):
        rgba = model.geom_rgba[i].copy()
        material = model.geom_matid[i]
        if material >= 0:
            rgba = model.mat_rgba[material].copy()
        geom = {"id": i, "name": model.geom(i).name or f"geom_{i}", "body_id": int(model.geom_bodyid[i]),
                "type": types.get(int(model.geom_type[i]), "box"), "size": model.geom_size[i].tolist(),
                "rgba": rgba.tolist(), "group": int(model.geom_group[i])}
        name = geom["name"]
        geom["category"] = ("fire" if name == "live_fire" else "occluder" if name == "live_occluder"
                            else "tool" if name.startswith("live_extinguisher")
                            else "robot" if model.geom_group[i] in (1, 2) else "env")
        if model.geom_dataid[i] >= 0 and geom["type"] == "mesh":
            geom["mesh_url"] = f"/assets/unitree_g1/mesh_{model.geom_dataid[i]}.json"
        geoms.append(geom)
    return {"model_id": MODEL_ID, "simulation_identity": simulation_identity(), "source": SOURCE, "license": "BSD-3-Clause", "license_url": "/assets/unitree_g1/LICENSE",
            "coordinate_system": "SI metres; MuJoCo Z-up, robot +X forward, camera-left +Y; quaternions wxyz",
            "motion": "Predefined authored poses, fixed-base G1, finite-force position servos; not a trained policy",
            "tool": {"mass_kg": .55, "mount": "right_wrist_yaw_link", "site": "live_nozzle", "heading_axis": "+Z"},
            "geoms": geoms,
            "joints": [{"name": model.joint(i).name, "qpos_adr": int(model.jnt_qposadr[i]), "dof_adr": int(model.jnt_dofadr[i]),
                        "axis": model.jnt_axis[i].tolist(), "range": model.jnt_range[i].tolist(), "body_id": int(model.jnt_bodyid[i])} for i in range(model.njnt)],
            "bodies": [{"id": i, "name": model.body(i).name, "parent_id": int(model.body_parentid[i])} for i in range(model.nbody)],
            "camera": {"name": "live_camera", "id": model.camera("live_camera").id, "fovy": float(model.cam_fovy[model.camera("live_camera").id])},
            "targets": TARGETS, "presets": build_presets(model)}
