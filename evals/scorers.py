"""Independent outcome checks. No ground truth is passed to an inference provider."""
import math


def mobile_score(metrics):
    """Re-derive the release outcome from authoritative mode-specific measurements."""
    targets = metrics.get("targets", [])
    exposure_ok = bool(targets) and all(
        type(t.get("best_valid_exposure_s")) in (int, float)
        and math.isfinite(t["best_valid_exposure_s"])
        and t["best_valid_exposure_s"] >= 2.0 - 1e-4
        and t.get("suppressed_at_s") is not None for t in targets)
    collisions = metrics.get("unintended_collision_count", -1)
    outcome = exposure_ok and collisions == 0
    return {"simulation_success": outcome, "all_target_exposure": exposure_ok,
            "collision_count": collisions, "measurement_consistent": outcome == metrics.get("success"),
            "metric_contract": "mobile_exposure_v1"}


def replay_exposure(scene, trajectory, metrics):
    """Recompute nozzle geometry, range, occlusion and contacts from saved MuJoCo qpos.

    This is an audit of recorded frames, not another physics owner. Physics remains
    authoritative. qpos quantization permits a two-frame exposure tolerance.
    """
    import mujoco
    import numpy as np
    model = mujoco.MjModel.from_xml_string(scene["mjcf"])
    data = mujoco.MjData(model)
    site = model.site("nozzle").id
    names = [model.geom(i).name for i in range(model.ngeom)]
    expected_contacts = {frozenset(p) for p in [
        ("floor", "robot_shin_l"), ("floor", "robot_shin_r"),
        ("robot_torso", "robot_arm"), ("robot_torso", "robot_leg_l"),
        ("robot_torso", "robot_leg_r")]}
    events = {e["frame"]: e for e in trajectory["fx"]["spray"]}
    positions = {f["id"]: np.asarray(f["pos"]) for f in trajectory["fx"]["fires"]}
    longest = {fid: 0 for fid in positions}
    current = dict(longest)
    active = None
    for i, qpos in enumerate(trajectory["qpos"]):
        if i in events:
            event = events[i]
            active = event["target_id"] if event["on"] else None
        if not active:
            for fid in current:
                current[fid] = 0
            continue
        data.qpos[:] = qpos
        mujoco.mj_forward(model, data)
        origin = data.site_xpos[site]
        direction = data.site_xmat[site].reshape(3, 3)[:, 2]
        delta = positions[active] - origin
        distance = float(np.linalg.norm(delta))
        angle = math.degrees(math.acos(float(np.clip(direction @ delta / max(distance, 1e-12), -1, 1))))
        hit = np.full(1, -1, dtype=np.int32)
        ray = mujoco.mj_ray(model, data, origin, delta / max(distance, 1e-12),
                            np.array([1, 0, 0, 0, 0, 0], dtype=np.uint8), True, -1, hit)
        collision = any((names[c.geom1].startswith(("robot_", "ext_"))
                         or names[c.geom2].startswith(("robot_", "ext_")))
                        and frozenset((names[c.geom1], names[c.geom2])) not in expected_contacts
                        for c in data.contact)
        valid = .35 <= distance <= 3.5 and angle <= 5 and (ray < 0 or ray >= distance - .01) and not collision
        current[active] = current[active] + 1 if valid else 0
        longest[active] = max(longest[active], current[active])
    durations = {fid: max(0, n - 1) / trajectory["fps"] for fid, n in longest.items()}
    consistent = all(abs(durations[t["target_id"]] - t["best_valid_exposure_s"]) <= 2 / trajectory["fps"] + 1e-4
                     for t in metrics["targets"])
    return {"replay_exposure_consistent": consistent, "audited_continuous_exposure_s": durations}


def acceptance(rows, baseline_available):
    locked = [r for r in rows if r["split"] == "locked_test" and r["provider"] == "wandb"]
    success = sum(r.get("simulation_success", False) for r in locked)
    complete = len(locked) == 16 and len({r.get('case_id') for r in locked}) == 8
    return {"candidate_promoted": False,
            "eligible_for_review": complete and baseline_available
                and success / len(locked) >= .9
                and all(r.get("collision_count", -1) == 0 for r in locked)
                and all(r.get("valid", False) for r in locked),
            "locked_success_count": success, "locked_attempt_count": len(locked),
            "locked_test_complete": complete,
            "baseline_comparison_available": baseline_available,
            "additional_required_gates": "rejection/staleness suites and browser acceptance must pass; promotion is separate"}
