"""Unit/engine checks. Mocked Cosmos outputs here are NOT acceptance evidence."""
import json
import base64
import time

import numpy as np
import pytest
from fastapi import HTTPException

from scene2real import config, cosmos
from scene2real.live import LiveSession


@pytest.fixture
def session(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "RUNS_DIR", tmp_path)
    return LiveSession(start_thread=False)


def authorize_for_physics_test(s, pose):
    """Test-only authorization, never used in the production request path."""
    s._set_pose(pose)
    s.decision = {"status": "ready"}
    s.lease_until = time.monotonic() + 60


@pytest.mark.parametrize("pose", ["left", "center", "right"])
def test_actual_ray_suppresses_three_targets(session, pose):
    session.set_scene({"scenario": pose})
    authorize_for_physics_test(session, pose)
    session.step(2200)
    assert session.metrics["hit_s"] > 1
    assert session.intensity < .8
    assert np.all(np.isfinite(session.data.qpos))
    for j in range(session.model.njnt):
        if session.model.jnt_limited[j]:
            actual = session.data.qpos[session.model.jnt_qposadr[j]]
            low, high = session.model.jnt_range[j]
            assert low - .03 <= actual <= high + .03
    limits = session.model.actuator_forcerange
    assert np.all(session.data.actuator_force >= limits[:, 0] - 1e-6)
    assert np.all(session.data.actuator_force <= limits[:, 1] + 1e-6)


def test_obstacle_and_wrong_aim_do_not_suppress(session):
    session.set_scene({"scenario": "obscured"})
    authorize_for_physics_test(session, "center")
    session.step(2200)
    assert session.intensity == 1
    assert session.metrics["blocked_s"] > 1
    session.set_scene({"scenario": "center"})
    authorize_for_physics_test(session, "left")
    session.step(2200)
    assert session.intensity == 1
    assert session.metrics["miss_s"] > 1


def test_manual_motion_does_not_authorize_spray(session):
    original = session.data.qpos.copy()
    session.control({"action": "pose", "pose": "left"})
    session.step(400)
    assert np.max(np.abs(session.data.qpos - original)) > .05
    assert not session.spray["on"]
    assert session.intensity == 1


def record_for(s):
    state = s.state()
    return {"snapshot_id": "unit-test-only", "scene_revision": s.revision,
            "camera_pose": state["camera"], "state_seq": state["seq"], "image_file": "test.jpg"}


@pytest.mark.parametrize("raw,status", [
    ('{"fire_sources":[],"scene_description":"no visible flames"}', "no_fire"),
    ('{"fire_sources":[],"uncertain":true}', "uncertain"),
    ('malformed response', "invalid"),
])
def test_mocked_inference_fail_closed(session, monkeypatch, raw, status):
    monkeypatch.setattr(cosmos, "call_cosmos", lambda frames: raw)
    record = record_for(session)
    session._infer(record, session.directory / "test.jpg", session.request_generation, session.revision)
    assert session.decision["status"] == status
    session.step(100)
    assert not session.spray["on"]
    assert session.intensity == 1
    assert session.inferences[-1]["raw_text"] == raw


def test_mocked_failure_and_stale_response_cannot_authorize(session, monkeypatch):
    def fail(frames):
        raise cosmos.UpstreamError("unit test outage")
    monkeypatch.setattr(cosmos, "call_cosmos", fail)
    record = record_for(session)
    session._infer(record, session.directory / "test.jpg", session.request_generation, session.revision)
    assert session.decision["status"] == "failed"
    assert session.lease_until == 0
    previous_revision = session.revision
    session.set_scene({"scenario": "right"})
    session._infer(record, session.directory / "test2.jpg", session.request_generation - 1, previous_revision)
    assert session.inferences[-1]["status"] == "stale"
    assert session.decision["status"] == "idle"
    assert session.lease_until == 0


def test_response_lease_and_scene_edit_stop_spray(session):
    authorize_for_physics_test(session, "center")
    session.lease_until = time.monotonic() - 1
    session.step(1)
    assert session.decision["status"] == "stale"
    assert not session.spray["on"]
    authorize_for_physics_test(session, "center")
    session.set_scene({"scenario": "none"})
    assert session.intensity == 0
    assert session.decision["status"] == "idle"
    assert not session.spray["on"]


def test_invalid_scene_is_atomic_and_reference_is_smooth(session):
    old_revision = session.revision
    old_position = session.data.mocap_pos[session.fire_mocap].copy()
    with pytest.raises(ValueError):
        session.set_scene({"scenario": "right", "fire_y": float("nan")})
    assert session.revision == old_revision
    assert np.array_equal(session.data.mocap_pos[session.fire_mocap], old_position)
    session._set_pose("left")
    before = session.reference.copy()
    session.step(1)
    first_change = np.max(np.abs(session.reference - before))
    assert first_change < 1e-6  # Starts with zero velocity and acceleration.
    for _ in range(400):
        before = session.reference.copy()
        session.step(1)
        assert np.max(np.abs(session.reference - before)) <= .85 * session.model.opt.timestep + 1e-9


def test_contact_reacts_through_physics_with_finite_motor_forces(session):
    session._set_pose("center")
    session.step(2000)
    nozzle = session.data.site_xpos[session.nozzle_id].copy()
    # Deliberate collision fixture overlapping the wrist, not an acceptance scene.
    session.data.mocap_pos[session.obstacle_mocap] = [nozzle[0] - .1, nozzle[1], nozzle[2]]
    session.step(1)
    assert session.data.ncon > 0
    session.step(300)
    assert np.all(np.isfinite(session.data.qpos))
    assert np.all(np.isfinite(session.data.actuator_force))
    assert np.all(session.data.actuator_force >= session.model.actuator_forcerange[:, 0] - 1e-6)
    assert np.all(session.data.actuator_force <= session.model.actuator_forcerange[:, 1] + 1e-6)


def test_obstacle_state_and_partial_updates(session):
    session.set_scene({"obstacle": True})
    assert session.state()["obstacle"] is True
    session.set_scene({"fire_y": .3})
    assert session.state()["obstacle"] is True
    session.set_scene({"scenario": "right"})
    assert session.state()["obstacle"] is False
    session.set_scene({"scenario": "obscured"})
    assert session.state()["obstacle"] is True


def test_manual_preview_revokes_ready_and_invalidates_pending(session, monkeypatch):
    authorize_for_physics_test(session, "center")
    original_generation = session.request_generation
    record = record_for(session)
    session.control({"action": "pose", "pose": "left"})
    assert session.lease_until == 0
    assert session.decision["status"] == "idle"
    assert session.request_generation > original_generation
    monkeypatch.setattr(cosmos, "call_cosmos", lambda frames: '{"fire_sources":[]}')
    session._infer(record, session.directory / "late.jpg", original_generation, session.revision)
    assert session.inferences[-1]["status"] == "stale"
    assert session.decision["status"] == "idle"


@pytest.mark.parametrize("extra", [{"uncertain": True}, {"confidence": .3}, {"description": "Possible flame, cannot confirm"}])
def test_mocked_per_source_uncertainty_stops_spray(session, monkeypatch, extra):
    source = {"id": "F1", "bbox_2d": [450, 300, 550, 600], "timestamps_s": [0.0],
              "description": "Visible orange fire", **extra}
    raw = json.dumps({"fire_sources": [source]})
    monkeypatch.setattr(cosmos, "call_cosmos", lambda frames: raw)
    session._infer(record_for(session), session.directory / "test.jpg", session.request_generation, session.revision)
    assert session.decision["status"] == "uncertain"
    assert session.lease_until == 0


@pytest.mark.parametrize("unknowns,status", [
    (["Identity of the burning object", "Cause of the fire"], "ready"),  # actual cosmos_fire_obs_v4 response shape
    (["Whether the fire is real or a reflection"], "uncertain"),
    (["Fire location partially occluded"], "uncertain"),
])
def test_ordinary_unknowns_do_not_veto_visible_fire(session, monkeypatch, unknowns, status):
    source = {"id": "F1", "bbox_2d": [453, 300, 566, 600], "timestamps_s": [0.0], "description": "A bright orange flame on a table"}
    raw = json.dumps({"fire_sources": [source], "cause": "Unknown", "depth_m": 3.0, "unknowns": unknowns})
    monkeypatch.setattr(cosmos, "call_cosmos", lambda frames: raw)
    session._infer(record_for(session), session.directory / "test.jpg", session.request_generation, session.revision)
    assert session.decision["status"] == status


def test_snapshot_save_works_without_cosmos_and_preserves_permission(session, monkeypatch):
    import cv2
    monkeypatch.setenv("SCENE2REAL_LIVE_COSMOS", "0")
    def forbidden(*args):
        raise AssertionError("Saving a camera image must never invoke Cosmos")
    monkeypatch.setattr(cosmos, "call_cosmos", forbidden)
    state = session.state()
    success, jpeg = cv2.imencode(".jpg", np.zeros((24, 32, 3), dtype=np.uint8))
    assert success
    body = {"snapshot_id": "camera-unit-save", "scene_revision": state["scene_revision"], "state_seq": state["seq"],
            "camera_pose": state["camera"], "image": "data:image/jpeg;base64," + base64.b64encode(jpeg).decode()}
    before_decision = session.decision.copy()
    before_generation = session.request_generation
    result = session.capture_snapshot(body)
    saved = result["saved_snapshot"]
    assert (session.directory / saved["image_file"]).read_bytes() == jpeg.tobytes()
    assert saved["inference_requested"] is False
    assert saved["source"] == "robot_camera"
    assert session.decision == before_decision
    assert session.request_generation == before_generation
    assert session.inferences == []
    with pytest.raises(HTTPException) as exc:
        session.submit(body)
    assert exc.value.status_code == 503
    assert session.lease_until == 0


def test_evidence_download_survives_in_memory_session_loss(session, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from scene2real import live
    monkeypatch.setattr(live, "SESSIONS", {session.id: session})
    camera = session.directory / "camera_saved.jpg"
    camera.write_bytes(b"saved camera evidence")
    recording = session.directory / "recording_saved.webm"
    recording.write_bytes(b"\x1aE\xdf\xa3saved recording")
    app = FastAPI()
    app.include_router(live.router)
    client = TestClient(app)
    saved_evidence = client.get(f"/api/live/{session.id}/evidence")
    assert saved_evidence.status_code == 200
    live.SESSIONS.clear()  # Simulates a server restart: files persist, state does not.
    archived = client.get(f"/api/live/{session.id}/evidence")
    assert archived.status_code == 200
    assert archived.json()["archived"] is True
    assert archived.json()["live"] is False
    assert archived.json()["state_is_historical"] is True
    for path in (camera, recording):
        downloaded = client.get(f"/api/live/{session.id}/evidence/{path.name}")
        assert downloaded.status_code == 200
        assert downloaded.content == path.read_bytes()
    assert live.SESSIONS == {}  # Reading historical evidence starts no simulation.
    assert client.get("/api/live/invalid-id/evidence").status_code == 400
    assert client.get("/api/live/000000000000/evidence").status_code == 404


def test_archive_without_exported_evidence_has_events_and_provenance(session, monkeypatch):
    from scene2real import live
    monkeypatch.setattr(live, "SESSIONS", {})
    archived = live.evidence(session.id)
    assert archived["archived"] is True
    assert archived["live"] is False
    assert archived["state_is_historical"] is False
    assert archived["events"]
    assert archived["provenance"]["engine"] == "MuJoCo"
