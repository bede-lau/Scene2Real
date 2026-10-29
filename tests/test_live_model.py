"""Mechanical provenance and dynamic preset execution regression checks."""
import builtins
import json
from pathlib import Path

import mujoco
import numpy as np
import pytest

from scene2real.live_model import ASSET_DIR, BROWSER_DIR, TARGETS, build_presets, create_data, get_model, manifest


def test_reference_joint_mechanics_and_inertias_are_preserved():
    reference = mujoco.MjModel.from_xml_path(str(ASSET_DIR / "g1.xml"))
    model = get_model()
    assert model.nq == 29  # explicitly fixed pelvis, no floating-base balancing
    assert np.all(model.opt.gravity == [0, 0, -9.81])
    assert not np.any(model.body_gravcomp)
    for j in range(model.njnt):
        original = reference.joint(model.joint(j).name).id
        np.testing.assert_allclose(model.jnt_axis[j], reference.jnt_axis[original])
        np.testing.assert_allclose(model.jnt_range[j], reference.jnt_range[original])
    for b in range(1, reference.nbody):
        derived = model.body(reference.body(b).name).id
        np.testing.assert_allclose(model.body_mass[derived], reference.body_mass[b])
        np.testing.assert_allclose(model.body_inertia[derived], reference.body_inertia[b])
    assert np.all(model.actuator_forcelimited)
    assert np.all(np.isfinite(model.actuator_forcerange))


@pytest.mark.parametrize("label", ["left", "center", "right"])
def test_dynamic_authored_pose_hits_its_target_and_wall_blocks(label):
    model = get_model()
    data = create_data(model)
    pose = build_presets(model)[label]
    fire = int(model.body("live_fire_body").mocapid[0])
    blocker = int(model.body("live_occluder_body").mocapid[0])
    data.mocap_pos[fire] = TARGETS[label]
    start = data.ctrl.copy()
    goal = np.array([pose[model.actuator(i).name] for i in range(model.nu)])
    for k in range(2000):
        s = min(k * model.opt.timestep / 1.5, 1)
        s = s * s * (3 - 2 * s)
        data.ctrl[:] = start + (goal - start) * s
        mujoco.mj_step(model, data)
    assert np.all(np.isfinite(data.qpos))
    assert np.all(data.qpos >= model.jnt_range[:, 0] - .001)
    assert np.all(data.qpos <= model.jnt_range[:, 1] + .001)
    site = model.site("live_nozzle").id
    origin = data.site_xpos[site].copy()
    direction = data.site_xmat[site].reshape(3, 3)[:, 2].copy()
    geom_id = np.full(1, -1, dtype=np.int32)
    groups = np.array([1, 0, 0, 1, 0, 0], dtype=np.uint8)
    dist = mujoco.mj_ray(model, data, origin, direction, groups, 1, -1, geom_id)
    assert dist > 0
    assert geom_id[0] == model.geom("live_fire").id
    data.mocap_pos[blocker] = [1.35, 0, .85]
    mujoco.mj_forward(model, data)
    blocked_dist = mujoco.mj_ray(model, data, origin, direction, groups, 1, -1, geom_id)
    assert 0 < blocked_dist < dist
    assert geom_id[0] == model.geom("live_occluder").id


def test_browser_mesh_exports_compiled_local_vertices_without_static_writes(monkeypatch):
    model = get_model()
    browser_dir = BROWSER_DIR.resolve()

    def is_browser_asset(path):
        resolved = Path(path).resolve()
        return resolved == browser_dir or browser_dir in resolved.parents

    def deny_mutation(path, *args, **kwargs):
        if is_browser_asset(path):
            raise PermissionError(f"read-only browser asset: {path}")

    original_open = builtins.open

    def deny_file_write(file, mode="r", *args, **kwargs):
        if any(flag in mode for flag in ("w", "a", "x", "+")) and is_browser_asset(file):
            raise PermissionError(f"read-only browser asset: {file}")
        return original_open(file, mode, *args, **kwargs)

    for method in ("mkdir", "write_text", "write_bytes", "touch"):
        monkeypatch.setattr(Path, method, deny_mutation)
    monkeypatch.setattr(builtins, "open", deny_file_write)

    exported = manifest(model)
    assert len(exported["joints"]) == 29
    assert exported["license"] == "BSD-3-Clause"
    assert exported["camera"]["name"] == "live_camera"
    from scene2real.live_model import ROOT
    for geom in exported["geoms"]:
        if geom["type"] != "mesh":
            continue
        path = ROOT / "static" / geom["mesh_url"].lstrip("/")
        mesh = json.loads(path.read_text())
        mesh_id = int(model.geom_dataid[geom["id"]])
        va, vn = int(model.mesh_vertadr[mesh_id]), int(model.mesh_vertnum[mesh_id])
        np.testing.assert_allclose(np.asarray(mesh["vertices"]).reshape(-1, 3), model.mesh_vert[va:va + vn], atol=1e-7)
        assert max(mesh["indices"]) < vn
