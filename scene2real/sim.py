"""Headless MuJoCo simulation of the aim_spray_demo skill."""
from __future__ import annotations

import math

import mujoco
import numpy as np

from .scene import check_reachable

SUPPORTED_SKILLS = {"aim_spray_demo"}
FPS = 30
RAISE_END_S = 1.5
SPRAY_ON_S = 2.0
THRESH_DEG = 5.0
HOLD_REQ_S = 2.0
ELBOW_TARGET = -0.5
REST = {"torso_yaw": 0.0, "shoulder_yaw": 0.0, "shoulder_pitch": -0.35, "elbow": -0.4}
JOINTS = ["torso_yaw", "shoulder_yaw", "shoulder_pitch", "elbow"]
RULE = ("error<=5deg for >=2.0s continuous sim time AND 0 unintended collisions "
        "(attachment contacts excluded)")
ARM_CHAIN = {"robot_uarm", "robot_fore", "robot_hand", "ext_body"}
TYPE_NAMES = {mujoco.mjtGeom.mjGEOM_BOX: "box", mujoco.mjtGeom.mjGEOM_SPHERE: "sphere",
              mujoco.mjtGeom.mjGEOM_CAPSULE: "capsule", mujoco.mjtGeom.mjGEOM_CYLINDER: "cylinder",
              mujoco.mjtGeom.mjGEOM_PLANE: "plane"}
TYPE_NDIM = {"box": 3, "sphere": 1, "capsule": 2, "cylinder": 2, "plane": 3}


def _group(name: str) -> str:
    if name.startswith("robot_"):
        return "robot"
    if name.startswith("ext_"):
        return "extinguisher"
    if name.startswith("fire_"):
        return "fire"
    return "env"


def _solve_pose(model, target):
    """Joint targets so the nozzle axis points from the nozzle at `target` (damped GN)."""
    d = mujoco.MjData(model)
    jadr = {n: model.jnt_qposadr[mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, n)] for n in JOINTS}
    lo = {n: model.jnt_range[mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, n)] for n in JOINTS}
    sid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_SITE, "nozzle")
    target = np.asarray(target, float)

    def resid(q):
        for n, v in zip(JOINTS, q):
            d.qpos[jadr[n]] = v
        mujoco.mj_forward(model, d)
        v = target - d.site_xpos[sid]
        return d.site_xmat[sid].reshape(3, 3)[:, 2] - v / np.linalg.norm(v)

    q = np.array([math.atan2(target[1], target[0]), 0.0, -1.2, ELBOW_TARGET])
    free = [0, 1, 2]
    lam = 1e-3
    r = resid(q)
    for _ in range(100):
        if np.linalg.norm(r) < 1e-9:
            break
        J = np.zeros((3, len(free)))
        for c, i in enumerate(free):
            qq = q.copy()
            qq[i] += 1e-6
            J[:, c] = (resid(qq) - r) / 1e-6
        step = -np.linalg.solve(J.T @ J + lam * np.eye(len(free)), J.T @ r)
        step = np.clip(step, -0.3, 0.3)
        qn = q.copy()
        qn[free] += step
        for i, n in enumerate(JOINTS):
            qn[i] = min(max(qn[i], lo[n][0]), lo[n][1])
        rn = resid(qn)
        if np.linalg.norm(rn) < np.linalg.norm(r):
            q, r, lam = qn, rn, max(lam / 3, 1e-9)
        else:
            lam *= 5
    return q


def _quat(xmat):
    out = np.zeros(4)
    mujoco.mju_mat2Quat(out, xmat)
    return out


def simulate(scene: dict, skill: dict) -> tuple[dict, dict]:
    name = (skill or {}).get("name")
    if name not in SUPPORTED_SKILLS:
        raise ValueError(f"unsupported skill '{name}'; supported: {sorted(SUPPORTED_SKILLS)}")
    tid = skill.get("target_id")
    fires = scene.get("fires") or {}
    if tid not in fires:
        raise ValueError(f"target '{tid}' is not mapped in this scene")
    ok, reason = check_reachable(scene, tid)
    if not ok:
        raise ValueError(reason)
    mjcf = scene.get("mjcf")
    if not mjcf and scene.get("mjcf_path"):
        with open(scene["mjcf_path"]) as fh:
            mjcf = fh.read()
    model = mujoco.MjModel.from_xml_string(mjcf)
    data = mujoco.MjData(model)
    dt = float(model.opt.timestep)
    duration = float(scene.get("settings", {}).get("duration_s", 6.0))
    target = np.array(fires[tid]["pos"], float)

    goal = _solve_pose(model, target)
    start = np.array([REST[n] for n in JOINTS])
    jids = [mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, n) for n in JOINTS]
    qadr = [model.jnt_qposadr[j] for j in jids]
    for a, v in zip(qadr, start):
        data.qpos[a] = v
    data.ctrl[:] = start
    mujoco.mj_forward(model, data)

    sid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_SITE, "nozzle")
    # geoms + classification tables
    ng = model.ngeom
    gnames = [mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_GEOM, i) for i in range(ng)]
    gbody = [mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_BODY, int(model.geom_bodyid[i])) for i in range(ng)]
    parent = {}
    for b in range(model.nbody):
        parent[b] = int(model.body_parentid[b])
    robotish = [_group(n) in ("robot", "extinguisher") for n in gnames]
    attach = {frozenset(p) for p in (("robot_torso", "robot_uarm"), ("robot_legs", "robot_torso"))}

    def unintended(g1, g2):
        if not (robotish[g1] or robotish[g2]):
            return False
        b1, b2 = gbody[g1], gbody[g2]
        if b1 == b2:
            return False
        if b1 in ARM_CHAIN and b2 in ARM_CHAIN:
            return False
        if frozenset((b1, b2)) in attach:
            return False
        return True

    geoms = []
    for i in range(ng):
        t = TYPE_NAMES.get(int(model.geom_type[i]))
        if t is None:
            raise ValueError(f"unsupported geom type for {gnames[i]}")
        geoms.append({"name": gnames[i], "type": t,
                      "size": [round(float(s), 4) for s in model.geom_size[i][:TYPE_NDIM[t]]],
                      "rgba": [round(float(c), 3) for c in model.geom_rgba[i]], "group": _group(gnames[i])})

    nsteps = int(round(duration / dt))
    n_frames = int(duration * FPS) + 1
    frame_steps = {int(round(k / FPS / dt)): k for k in range(n_frames)}
    frames, nozzle_fx, ang_frames = [], [], []
    errs = np.zeros(nsteps)
    pairs = {}
    run = best = 0
    for i in range(nsteps):
        t = i * dt
        s = min(t / RAISE_END_S, 1.0)
        s = s * s * (3 - 2 * s)
        data.ctrl[:] = start + (goal - start) * s
        pos = data.site_xpos[sid]
        axis = data.site_xmat[sid].reshape(3, 3)[:, 2]
        v = target - pos
        err = math.degrees(math.acos(max(-1.0, min(1.0, float(axis @ v) / np.linalg.norm(v)))))
        errs[i] = err
        if i in frame_steps:
            row = []
            for gi in range(ng):
                row.extend(round(float(x), 4) for x in data.geom_xpos[gi])
                row.extend(round(float(x), 4) for x in _quat(data.geom_xmat[gi]))
            frames.append(row)
            nozzle_fx.append([round(float(x), 4) for x in (*pos, *axis)])
            ang_frames.append(round(err, 3))
        mujoco.mj_step(model, data)
        for c in range(data.ncon):
            con = data.contact[c]
            g1, g2 = int(con.geom1), int(con.geom2)
            if unintended(g1, g2):
                pairs[tuple(sorted((gnames[g1], gnames[g2])))] = True
        run = run + 1 if err <= THRESH_DEG else 0
        best = max(best, run)
    if len(frames) < n_frames:  # final frame at t == duration
        mujoco.mj_forward(model, data)
        pos = data.site_xpos[sid]
        axis = data.site_xmat[sid].reshape(3, 3)[:, 2]
        v = target - pos
        err = math.degrees(math.acos(max(-1.0, min(1.0, float(axis @ v) / np.linalg.norm(v)))))
        row = []
        for gi in range(ng):
            row.extend(round(float(x), 4) for x in data.geom_xpos[gi])
            row.extend(round(float(x), 4) for x in _quat(data.geom_xmat[gi]))
        frames.append(row)
        nozzle_fx.append([round(float(x), 4) for x in (*pos, *axis)])
        ang_frames.append(round(err, 3))
    hold_s = best * dt
    col_list = [f"{a}|{b}" for a, b in sorted(pairs)]
    metrics = {"angle_error_deg_final": round(float(errs[-1]), 3),
               "angle_error_deg_min": round(float(errs.min()), 3),
               "hold_s": round(hold_s, 3), "duration_s": duration,
               "unintended_collisions": col_list, "unintended_collision_count": len(col_list),
               "success": bool(hold_s >= HOLD_REQ_S and not col_list), "rule": RULE}
    traj = {"fps": FPS, "duration_s": duration, "geoms": geoms, "frames": frames,
            "fx": {"fires": [{"id": f, "pos": fires[f]["pos"], "target": f == tid} for f in fires],
                   "spray": [{"frame": int(round(SPRAY_ON_S * FPS)), "on": True}],
                   "nozzle": nozzle_fx},
            "angle_error_deg": ang_frames}
    return metrics, traj
