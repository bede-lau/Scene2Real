"""Compatibility must never relocate or silently drop confirmed incident targets."""
import base64
import copy
import json
import time
import threading

from fastapi import FastAPI
from fastapi.testclient import TestClient
import numpy as np
import pytest

from scene2real import config, cosmos, live, live_model


def incident(position=None):
    return {"run_id": "r_compat", "state": "confirmed", "confirmed_targets": [
        {"fire_id": "T1", "template_position_m": position or list(live_model.TARGETS["left"]),
         "position_provenance": "operator-confirmed authored G1 anchor", "members": ["V1:A1"]}]}


@pytest.mark.parametrize("change", ["multiple", "r1_anchor", "unconfirmed", "missing_provenance", "nonfinite", "boolean"])
def test_incompatible_incidents_do_not_create_or_relocate_targets(change):
    run = incident()
    if change == "multiple":
        run["confirmed_targets"].append({**run["confirmed_targets"][0], "fire_id": "T2"})
    elif change == "r1_anchor":
        run["confirmed_targets"][0]["template_position_m"] = [4.0, 1.6, .5]
    elif change == "unconfirmed":
        run["state"] = "analysed"
    elif change == "missing_provenance":
        run["confirmed_targets"][0].pop("position_provenance")
    elif change == "nonfinite":
        run["confirmed_targets"][0]["template_position_m"][0] = float("inf")
    else:
        run["confirmed_targets"][0]["template_position_m"][0] = True
    original = copy.deepcopy(run)
    result = live.incident_compatibility(run)
    assert result["status"] == "unsupported_mode"
    assert result["target_ids"] == [t["fire_id"] for t in run["confirmed_targets"]]
    assert run == original


def test_server_handoff_uses_saved_confirmation_and_preserves_parent(tmp_path, monkeypatch):
    from scene2real import pipeline
    monkeypatch.setattr(config, "RUNS_DIR", tmp_path)
    monkeypatch.setattr(live, "SESSIONS", {})
    original_class = live.LiveSession
    monkeypatch.setattr(live, "LiveSession", lambda: original_class(start_thread=False, inference_provenance="mocked"))
    run = incident()
    monkeypatch.setattr(pipeline, "get_run", lambda _: run)
    app = FastAPI()
    app.include_router(live.router)
    client = TestClient(app)
    result = client.post("/api/live/from-incident", json={"parent_run_id": run["run_id"]})
    assert result.status_code == 200
    state = result.json()["state"]
    assert state["parent_run_id"] == run["run_id"]
    assert state["incident"]["target_ids"] == ["T1"]
    assert state["incident"]["placement_provenance"] == run["confirmed_targets"][0]["position_provenance"]
    assert state["fire"]["position"] == run["confirmed_targets"][0]["template_position_m"]
    assert state["incident_placement_matches"] is True
    assert state["spray"]["on"] is False
    assert state["decision"]["status"] == "idle"
    session = live.SESSIONS[state["session_id"]]
    assert json.loads((session.directory / "incident.json").read_text())["target_ids"] == ["T1"]
    assert json.loads((session.directory / "provenance.json").read_text())["simulation_identity"]["mode"] == "live_g1_fixed_base"
    session.set_scene({"scenario": "right"})
    assert session.state()["incident_placement_matches"] is False
    run["confirmed_targets"].append({**run["confirmed_targets"][0], "fire_id": "T2"})
    count = len(live.SESSIONS)
    unsupported = client.post("/api/live/from-incident", json={"parent_run_id": run["run_id"]}).json()
    assert unsupported["status"] == "unsupported_mode"
    assert unsupported["target_ids"] == ["T1", "T2"]
    assert len(live.SESSIONS) == count
    assert client.post("/api/live/from-incident", json={"parent_run_id": run["run_id"], "scenario": "left"}).status_code == 422


def test_identity_distinguishes_fixed_base_g1():
    identity = live_model.simulation_identity()
    assert identity["mode"] == "live_g1_fixed_base"
    assert identity["capabilities"]["walking"] is False
    assert identity["capabilities"]["max_targets"] == 1
    assert len(identity["source_asset_sha256"]) == 64
    assert len(identity["authored_model_sha256"]) == 64


def test_invalid_snapshot_invalidates_pending_generation(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "RUNS_DIR", tmp_path)
    session = live.LiveSession(start_thread=False, inference_provenance="mocked")
    session.decision = {"status": "pending"}
    generation = session.request_generation
    # JPEG framing is sufficient to reach authoritative metadata validation.
    body = {"image": "data:image/jpeg;base64," + base64.b64encode(b"\xff\xd8" + b"x" * 100).decode(),
            "snapshot_id": "stale", "state_seq": -1, "scene_revision": session.revision}
    with pytest.raises(live.HTTPException):
        session.capture_snapshot(body)
    assert session.request_generation > generation
    assert session.decision["status"] == "stale"
    assert session.lease_until == 0


def test_session_close_revokes_motion_and_joins_worker(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "RUNS_DIR", tmp_path)
    session = live.LiveSession()
    session.decision = {"status": "ready"}
    session.lease_until = time.monotonic() + 60
    session.close()
    assert session.closed
    assert session.lease_until == 0
    assert session.spray["on"] is False
    assert not session.worker.is_alive()


def test_disconnected_client_invalidates_pending_inference(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "RUNS_DIR", tmp_path)
    session = live.LiveSession()
    try:
        with session.lock:
            session.decision = {"status": "pending"}
            generation = session.request_generation
            session.last_active = time.monotonic() - live.CLIENT_HEARTBEAT_S - 1
        until = time.monotonic() + 1
        while session.decision["status"] == "pending" and time.monotonic() < until:
            time.sleep(.01)
        assert session.decision["status"] == "stale"
        assert session.request_generation > generation
        assert session.lease_until == 0
    finally:
        session.close()


def test_independent_sessions_have_distinct_authoritative_data(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "RUNS_DIR", tmp_path)
    first = live.LiveSession(start_thread=False)
    second = live.LiveSession(start_thread=False)
    before = second.data.mocap_pos.copy()
    first.set_scene({"scenario": "left", "obstacle": True})
    assert first.data is not second.data
    np.testing.assert_array_equal(second.data.mocap_pos, before)
    first.close()
    assert not second.closed


def test_event_queue_saturation_is_visible_without_blocking(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "RUNS_DIR", tmp_path)
    session = live.LiveSession(start_thread=False)
    before = live._EVENT_STATUS["dropped"]
    def full(_):
        raise live.queue.Full
    with monkeypatch.context() as scoped:
        scoped.setattr(live._EVENT_QUEUE, "put_nowait", full)
        session._event("physics", contacts=0)
    assert live._EVENT_STATUS["dropped"] == before + 1
    assert session.events[-1]["kind"] == "physics"


def test_live_milestones_link_session_parent_and_revision(tmp_path, monkeypatch):
    from scene2real import observability
    monkeypatch.setattr(config, "RUNS_DIR", tmp_path)
    calls = []
    monkeypatch.setattr(observability, "emit", lambda stage, **fields: calls.append((stage, fields)))
    session = live.LiveSession(start_thread=False, inference_provenance="mocked")
    session.incident = {"parent_run_id": "r_parent", "template_position_m": list(live_model.TARGETS["center"])}
    session._event("snapshot", snapshot_id="S1", state_seq=2)
    stage, event = calls[-1]
    assert stage == "live.snapshot"
    assert event["session_id"] == session.id
    assert event["parent_run_id"] == "r_parent"
    assert event["scene_revision"] == session.revision
    assert event["snapshot_id"] == "S1"
    assert event["simulation_identity"]["mode"] == "live_g1_fixed_base"
    count = len(calls)
    session._event("physics", contacts=0)
    assert len(calls) == count  # Physics-step data remains local.


def test_revocation_milestones_are_correlated_and_transition_only(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "RUNS_DIR", tmp_path)
    session = live.LiveSession(start_thread=False)
    session.incident = {"parent_run_id": "r_parent", "template_position_m": list(live_model.TARGETS["center"])}
    session.decision = {"status": "ready", "snapshot_id": "S1"}
    session.lease_until = time.monotonic() + 30
    session.control({"action": "stop"})
    events = [e for e in session.events if e["kind"] == "permission_revoked"]
    last = events[-1]
    assert last["snapshot_id"] == "S1" and last["parent_run_id"] == "r_parent"
    assert last["request_generation"] == session.request_generation
    assert last["previous_status"] == "ready" and last["status"] == "idle"
    session._revoke("idle", last["reason"])
    assert len([e for e in session.events if e["kind"] == "permission_revoked"]) == len(events)


def test_actual_cosmos_boundary_receives_explicit_thread_context(tmp_path, monkeypatch):
    from scene2real import observability
    monkeypatch.setattr(config, "RUNS_DIR", tmp_path)
    session = live.LiveSession(start_thread=False, inference_provenance="mocked")
    session.incident = {"parent_run_id": "r_parent", "template_position_m": list(live_model.TARGETS["center"])}
    seen = {}
    def infer(_):
        seen.update(observability._CONTEXT.get())
        return '{"fire_sources":[]}'
    monkeypatch.setattr(cosmos, "call_cosmos", infer)
    record = {"snapshot_id": "S_ctx", "camera_pose": session.state()["camera"], "image_file": "test.jpg"}
    session._infer(record, session.directory / "test.jpg", session.request_generation, session.revision)
    assert seen["session_id"] == session.id and seen["parent_run_id"] == "r_parent"
    assert seen["snapshot_id"] == "S_ctx" and seen["scene_revision"] == session.revision
    assert seen["stage"] == "live.cosmos" and seen["model_id"] == cosmos.MODEL_ID


def test_slow_response_evidence_io_does_not_stop_physics_and_scene_edit_wins(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "RUNS_DIR", tmp_path)
    session = live.LiveSession(inference_provenance="mocked")
    started, release = threading.Event(), threading.Event()
    original = live._write_json
    def delayed(path, value):
        if path.name.endswith("_response.json") and not started.is_set():
            started.set()
            release.wait(timeout=3)
        return original(path, value)
    monkeypatch.setattr(live, "_write_json", delayed)
    monkeypatch.setattr(cosmos, "call_cosmos", lambda _: '{"fire_sources":[]}')
    record = {"snapshot_id": "S_slow", "camera_pose": session.state()["camera"], "image_file": "test.jpg"}
    generation, revision = session.request_generation, session.revision
    worker = threading.Thread(target=session._infer, args=(record, session.directory / "test.jpg", generation, revision))
    worker.start()
    try:
        assert started.wait(timeout=1)
        before = float(session.data.time)
        until = time.monotonic() + 1
        while float(session.data.time) < before + .04 and time.monotonic() < until:
            time.sleep(.01)
        assert float(session.data.time) >= before + .04
        session.set_scene({"scenario": "right"})
        release.set()
        worker.join(timeout=2)
        entry = session.inferences[-1]
        assert entry["status"] == "stale"
        assert entry["stale_flags"]["revision_changed"] and entry["stale_flags"]["generation_changed"]
        assert entry["snapshot_revision"] == revision and entry["current_revision"] == session.revision
        assert "discarded" in entry["detail"]
        assert not session.spray["on"] and session.decision["status"] == "idle"
    finally:
        release.set()
        worker.join(timeout=2)
        session.close()
