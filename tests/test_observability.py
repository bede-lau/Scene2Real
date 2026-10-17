"""Local/remote telemetry cannot authorize actions or block simulator threads."""
import json
import queue
import threading
import time
from pathlib import Path

import pytest

from scene2real import config, observability as obs, pipeline, records


@pytest.fixture(autouse=True)
def telemetry(tmp_path, monkeypatch):
    assert obs.flush(2)
    monkeypatch.setattr(config, "RUNS_DIR", tmp_path)
    monkeypatch.setitem(config.TELEMETRY, "weave", "skipped: test")
    yield tmp_path
    assert obs.flush(2)


def events(path):
    assert obs.flush(2)
    return [json.loads(line) for line in path.read_text().splitlines()]


def test_context_links_separate_requests_and_explicit_background_thread(telemetry):
    with obs.context(run_id="r_parent"):
        obs.emit("planner.attempt", provider="wandb", model_id="candidate")
    thread = threading.Thread(target=lambda: obs.emit("live.command", session_id="s1", parent_run_id="r_parent",
                                                      scene_revision=3, snapshot_id="snap1"))
    thread.start()
    thread.join()
    first = events(telemetry / "r_parent/telemetry.jsonl")[0]
    second = events(telemetry / "live_s1/telemetry.jsonl")[0]
    assert first["trace_group_id"] == second["trace_group_id"] == "r_parent"
    assert first["event_id"] != second["event_id"]
    assert second["scene_revision"] == 3 and second["snapshot_id"] == "snap1"
    assert obs.emit("unscoped") is None


def test_sanitize_secrets_signed_credentials_and_nonfinite(telemetry, monkeypatch):
    monkeypatch.setenv("WANDB_API_KEY", "secret-value-123456789")
    obs.emit("planner.failure", run_id="r_test", api_key="abc", headers={"Authorization": "Bearer abc"},
             error="secret-value-123456789 Bearer abcdef https://user:pass@host/file?X-Amz-Signature=secret",
             nested={"password": "abc", "number": float("nan")})
    raw = (events(telemetry / "r_test/telemetry.jsonl"))[0]
    encoded = json.dumps(raw)
    assert "secret-value" not in encoded and "abcdef" not in encoded and "user:pass" not in encoded
    assert "X-Amz" not in encoded
    assert raw["nested"]["number"] is None
    assert raw["api_key"] == "[redacted]" and raw["headers"] == "[redacted]"


def test_queue_full_drops_only_telemetry(telemetry, monkeypatch):
    before = obs.status()["dropped"]
    def full(item):
        raise queue.Full
    monkeypatch.setattr(obs._QUEUE, "put_nowait", full)
    assert obs.emit("simulation.outcome", run_id="r_test") is None
    assert obs.status()["dropped"] == before + 1


def test_remote_failure_preserves_local_evidence(telemetry, monkeypatch):
    before = obs.status()["weave_errors"]
    monkeypatch.setitem(config.TELEMETRY, "weave", "ok")
    def fail(event):
        raise RuntimeError("private-token-must-not-leak")
    monkeypatch.setattr(obs, "_send_weave", fail)
    obs.emit("recording.export", run_id="r_test", outcome="ok")
    assert events(telemetry / "r_test/telemetry.jsonl")[0]["outcome"] == "ok"
    assert obs.status()["weave_errors"] == before + 1
    assert "private-token" not in json.dumps(obs.status())


def test_stalled_remote_does_not_stall_local_worker(telemetry, monkeypatch):
    release, entered = threading.Event(), threading.Event()
    monkeypatch.setitem(config.TELEMETRY, "weave", "ok")
    def stall(event):
        entered.set()
        release.wait(2)
    monkeypatch.setattr(obs, "_send_weave", stall)
    try:
        obs.emit("simulation.started", run_id="r_test")
        assert entered.wait(1)
        start = time.monotonic()
        obs.emit("simulation.outcome", run_id="r_other", metrics={"success": True})
        assert time.monotonic() - start < .2
        path = telemetry / "r_other/telemetry.jsonl"
        until = time.monotonic() + 1
        while not path.exists() and time.monotonic() < until:
            time.sleep(.01)
        assert path.exists()
    finally:
        release.set()


def test_local_write_failure_does_not_escape(telemetry, monkeypatch):
    before = obs.status()["local_errors"]
    monkeypatch.setattr(Path, "open", lambda *args, **kwargs: (_ for _ in ()).throw(PermissionError()))
    assert obs.emit("simulation.outcome", run_id="r_test")
    assert obs.flush(1)
    assert obs.status()["local_errors"] == before + 1


def test_evidence_is_immutable_sanitized_and_hash_addressed(telemetry):
    one = records.evidence("r_test", "review", {"fire_ids": ["F1"], "api_key": "secret"})
    two = records.evidence("r_test", "review", {"fire_ids": ["F2"]})
    assert one["path"] != two["path"]
    path = telemetry / "r_test" / "evidence" / Path(one["path"]).name
    assert json.loads(path.read_text())["api_key"] == "[redacted]"
    assert records.evidence("r_test", "review", {"fire_ids": ["F1"], "api_key": "secret"}) == one


def test_old_saved_run_load_preserves_semantics(telemetry):
    old = {"run_id": "r_old", "state": "completed", "confirmed_target": {"fire_id": "F1"}}
    records.save(old)
    assert records.load("r_old") == old
    assert "simulation_identity" not in records.load("r_old")


def test_mode_identity_does_not_relabel_robot():
    mobile = pipeline._identity({"mjcf": "<mobile/>", "template_id": "wh_mobile_v1"}, "mobile")
    legacy = pipeline._identity({"mjcf": "<fixed/>", "template_id": "wh_aisle_v1"}, "legacy")
    assert mobile["model_id"] == "r1_reduced_control_v1"
    assert "scripted_walk" in mobile["capabilities"]
    assert "fixed_base" in legacy["capabilities"]
    assert mobile["source_asset_sha256"] != legacy["source_asset_sha256"]
    assert "g1" not in json.dumps(mobile)


def test_unsafe_id_does_not_write_outside_run_tree(telemetry):
    assert obs.emit("ingest", run_id="../escape") is None
    assert obs.emit("ingest", session_id="/tmp/escape") is None


def test_mocked_campaign_cannot_be_mislabeled_fresh(telemetry, monkeypatch):
    monkeypatch.setenv("SCENE2REAL_EVIDENCE_PROVENANCE", "mocked")
    obs.emit("cosmos.validation", run_id="r_test", provenance="live")
    assert events(telemetry / "r_test/telemetry.jsonl")[0]["provenance"] == "mocked"
