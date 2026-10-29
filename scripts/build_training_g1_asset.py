"""Build a compact visual-only G1 asset from the pinned Menagerie model.

Run from the repository root with the project's MuJoCo environment. Vertex
clustering reduces bandwidth; pose transforms come from the existing authored
left/centre/right references, not from a trained robot controller.
"""
from __future__ import annotations

import json
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
    return {"schema": "scene2real-training-g1-visual-v1", "source": SOURCE, "commit": COMMIT,
            "license": "/assets/unitree_g1/LICENSE", "cluster_metres": CLUSTER_METRES,
            "geometries": geometries, "meshes": meshes, "poses": poses}


if __name__ == "__main__":
    asset = generate()
    OUTPUT.write_text(json.dumps(asset, separators=(",", ":")), encoding="utf-8")
    print(f"Wrote {OUTPUT.relative_to(ROOT)} ({OUTPUT.stat().st_size:,} bytes)")
