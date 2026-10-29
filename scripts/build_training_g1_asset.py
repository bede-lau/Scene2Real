"""Build a compact visual-only G1 asset from the pinned Menagerie model.

Run from the repository root with the project's MuJoCo environment. Vertex
clustering reduces bandwidth; pose transforms come from the existing authored
left/centre/right references, not from a trained robot controller.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import mujoco
import numpy as np

from scene2real.live_model import COMMIT, SOURCE, build_presets, create_data, get_model

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "static/assets/unitree_g1/training-g1.json"
CLUSTER_METRES = 0.008


def compact_mesh(model, mesh_id):
    va, vn = int(model.mesh_vertadr[mesh_id]), int(model.mesh_vertnum[mesh_id])
    fa, fn = int(model.mesh_faceadr[mesh_id]), int(model.mesh_facenum[mesh_id])
    vertices = np.asarray(model.mesh_vert[va:va + vn], dtype=float)
    faces = np.asarray(model.mesh_face[fa:fa + fn], dtype=int)
    cells = np.rint(vertices / CLUSTER_METRES).astype(np.int32)
    _, inverse = np.unique(cells, axis=0, return_inverse=True)
    counts = np.bincount(inverse)
    simplified = np.column_stack([np.bincount(inverse, weights=vertices[:, axis]) / counts for axis in range(3)])
    triangles = inverse[faces]
    triangles = triangles[(triangles[:, 0] != triangles[:, 1]) & (triangles[:, 1] != triangles[:, 2]) & (triangles[:, 2] != triangles[:, 0])]
    if not len(triangles):
        raise ValueError(f"Mesh {mesh_id} has no faces after simplification")
    return {"vertices": np.round(simplified, 4).reshape(-1).tolist(), "indices": triangles.reshape(-1).tolist()}


def generate():
    model = get_model()
    presets = build_presets(model)
    data = create_data(model)
    visible = [i for i in range(model.ngeom) if int(model.geom_group[i]) == 2]
    meshes = {}
    geometries = []
    for index in visible:
        kind = int(model.geom_type[index])
        if kind == int(mujoco.mjtGeom.mjGEOM_MESH):
            mesh_id = int(model.geom_dataid[index])
            meshes.setdefault(str(mesh_id), compact_mesh(model, mesh_id))
            geometry = {"type": "mesh", "mesh": mesh_id}
        elif kind == int(mujoco.mjtGeom.mjGEOM_CYLINDER):
            geometry = {"type": "cylinder", "size": np.round(model.geom_size[index], 5).tolist()}
        else:
            raise ValueError(f"Unexpected visible G1 geometry type {kind}")
        material = int(model.geom_matid[index])
        rgba = model.mat_rgba[material] if material >= 0 else model.geom_rgba[index]
        geometry.update(id=index, rgba=np.round(rgba, 4).tolist())
        geometries.append(geometry)

    poses = {}
    for name in ("rest", "left", "center", "right"):
        for joint, value in presets[name].items():
            data.qpos[int(model.jnt_qposadr[model.joint(joint).id])] = value
        mujoco.mj_forward(model, data)
        transforms = []
        for index in visible:
            quat = np.empty(4)
            mujoco.mju_mat2Quat(quat, data.geom_xmat[index])
            transforms.append(np.round(np.r_[data.geom_xpos[index], quat], 5).tolist())
        nozzle = model.site("live_nozzle").id
        poses[name] = {"geoms": transforms, "nozzle": np.round(data.site_xpos[nozzle], 5).tolist()}
    # Precompute two distance-matched walking clips with grounded stance feet.
    # This is kinematic illustration, not a physics rollout or learned policy.
    leg_indices = [j for j, geom in enumerate(visible) if any(part in model.body(int(model.geom_bodyid[geom])).name for part in ("hip_", "knee_", "ankle_"))]
    for joint, value in presets["rest"].items():
        data.qpos[int(model.jnt_qposadr[model.joint(joint).id])] = value
    mujoco.mj_forward(model, data)
    foot_bodies = [model.body(f"{side}_ankle_roll_link").id for side in ("left", "right")]
    foot_base = [data.xpos[body].copy() for body in foot_bodies]
    leg_addresses = [[int(model.jnt_qposadr[model.joint(f"{side}_{joint}_joint").id]) for joint in ("hip_pitch", "knee", "ankle_pitch")] for side in ("left", "right")]
    profiles = {}
    for name, distance in (("short", 0.462), ("long", 0.924)):
        frames = []
        stride = distance / 4
        for frame in range(49):
            p = frame / 48
            phase = min(3, int(p * 4))
            t = p * 4 - phase
            drop = 0.06 * min(1, p / 0.15, (1 - p) / 0.15)
            smooth = t * t * (3 - 2 * t)
            stance = phase % 2
            # Each supporting foot moves backwards locally by exactly the root
            # advance. The other foot lifts and swings forward to its next plant.
            if phase == 0: feet_x = [-stride * t, stride * smooth]
            elif phase == 1: feet_x = [-stride + 2 * stride * smooth, stride * (1 - t)]
            elif phase == 2: feet_x = [stride * (1 - t), stride * smooth]
            else: feet_x = [0, stride * (1 - t)]
            for joint, value in presets["rest"].items():
                data.qpos[int(model.jnt_qposadr[model.joint(joint).id])] = value
            for side in (0, 1):
                lift = 0 if side == stance else 0.055 * math.sin(math.pi * t)
                desired = foot_base[side][[0, 2]] + [feet_x[side], drop + lift]
                ids = leg_addresses[side]
                q = np.array([-0.35, 0.7, -0.35]) if drop + lift > 1e-6 else np.zeros(3)

                def residual(values):
                    data.qpos[ids] = values
                    mujoco.mj_forward(model, data)
                    return np.r_[data.xpos[foot_bodies[side]][[0, 2]] - desired, values.sum() * 0.4]

                for _ in range(60):
                    error = residual(q)
                    if np.linalg.norm(error) < 1e-7:
                        break
                    jac = np.column_stack([(residual(q + np.eye(3)[k] * 1e-5) - error) / 1e-5 for k in range(3)])
                    step = np.linalg.solve(jac.T @ jac + np.eye(3) * 1e-6, jac.T @ error)
                    q = np.clip(q - np.clip(step, -0.2, 0.2), [-1.2, -0.08, -0.87], [1.2, 2.0, 0.52])
                if np.linalg.norm(residual(q)) > 0.002:
                    raise ValueError(f"Walking foot pose could not be grounded: {name}, frame {frame}, side {side}")
            mujoco.mj_forward(model, data)
            transforms = []
            for j in leg_indices:
                geom = visible[j]
                quat = np.empty(4)
                mujoco.mju_mat2Quat(quat, data.geom_xmat[geom])
                transforms.append(np.round(np.r_[data.geom_xpos[geom], quat], 5).tolist())
            feet = [[round(float(data.xpos[body][0] - foot_base[i][0]), 5), round(float(data.xpos[body][2] - drop - foot_base[i][2]), 5)] for i, body in enumerate(foot_bodies)]
            frames.append({"geoms": transforms, "drop": round(drop, 5), "feet": feet, "stance": stance})
        profiles[name] = {"distance": distance, "frames": frames}
    return {"schema": "scene2real-training-g1-visual-v1", "source": SOURCE, "commit": COMMIT,
            "license": "/assets/unitree_g1/LICENSE", "cluster_metres": CLUSTER_METRES,
            "geometries": geometries, "meshes": meshes, "poses": poses, "walk": {"leg_indices": leg_indices, "profiles": profiles}}


if __name__ == "__main__":
    asset = generate()
    OUTPUT.write_text(json.dumps(asset, separators=(",", ":")), encoding="utf-8")
    print(f"Wrote {OUTPUT.relative_to(ROOT)} ({OUTPUT.stat().st_size:,} bytes)")
