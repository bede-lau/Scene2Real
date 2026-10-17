import json
import time

import pytest

from scene2real.scene import ZONES, build_scene, check_reachable, suggest_zone
from scene2real.sim import simulate

SKILL = {"name": "aim_spray_demo", "target_id": "F1"}


def _scene(zone):
    return build_scene([{"id": "F1"}], {"F1": zone}, "F1")


@pytest.mark.parametrize("zone", ["right_rack", "left_rack", "aisle_center", "loading_dock"])
def test_success(zone):
    sc = _scene(zone)
    assert check_reachable(sc, "F1")[0]
    t0 = time.time()
    m, traj = simulate(sc, SKILL)
    print(f"\n{zone}: {time.time() - t0:.2f}s {m}")
    assert m["success"] is True and m["unintended_collision_count"] == 0, m
    assert len(traj["frames"]) == 181 and len(traj["frames"][0]) == 7 * len(traj["geoms"])
    assert len(traj["fx"]["nozzle"]) == 181 == len(traj["angle_error_deg"])
    json.dumps(traj)


def test_behind_robot_rejected():
    sc = _scene("behind_robot")
    ok, reason = check_reachable(sc, "F1")
    assert not ok and "yaw" in reason
    with pytest.raises(ValueError):
        simulate(sc, SKILL)


def test_bad_inputs():
    sc = _scene("right_rack")
    with pytest.raises(ValueError):
        simulate(sc, {"name": "dance", "target_id": "F1"})
    with pytest.raises(ValueError):
        simulate(sc, {"name": "aim_spray_demo", "target_id": "F9"})
    with pytest.raises(ValueError):
        build_scene([{"id": "F1"}, {"id": "F2"}], {"F1": "right_rack"}, "F2")
    with pytest.raises(ValueError):
        build_scene([{"id": "F1"}], {"F1": "nowhere"}, "F1")


def test_replay_deterministic():
    sc = _scene("right_rack")
    m1, t1 = simulate(sc, SKILL)
    m2, t2 = simulate(sc, SKILL)
    assert m1 == m2 and t1 == t2


def test_misc():
    assert suggest_zone([0.0, 0, 0.2, 1]) == "left_rack"
    assert suggest_zone([0.7, 0, 0.9, 1]) == "right_rack"
    assert suggest_zone([0.4, 0, 0.6, 1]) == "aisle_center"
    assert suggest_zone(None) is None
    assert set(ZONES) >= {"left_rack", "right_rack", "aisle_center", "loading_dock", "behind_robot"}
