import json
import subprocess

import pytest
from fastapi.testclient import TestClient

from scene2real import config, cosmos, pipeline, planner, records, yolo
from scene2real.app import app

GOOD = {"fire_sources": [{"id": "F1", "timestamps_s": [1.0, 2.0], "bbox_normalized": [0.62, 0.4, 0.8, 0.71],
                          "description": "burning packaging"}],
        "cause": None, "scale": None, "depth_m": None, "unknowns": ["cause", "scale", "depth"]}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "RUNS_DIR", tmp_path / "runs")
    pipeline._RUNS.clear()
    monkeypatch.setattr(records, "archive", lambda run, **kw: "skipped: test")
    monkeypatch.setattr(yolo, "detect", lambda p: ([], "stub"))
    monkeypatch.setattr(planner, "call_wandb",
                        lambda fid, zone, desc, sup: ({"instruction": f"Aim at {fid}",
                                                       "skill": {"name": "aim_spray_demo", "target_id": fid}}, "stub-model"))
    return TestClient(app)


@pytest.fixture(scope="session")
def clip(tmp_path_factory):
    p = tmp_path_factory.mktemp("c") / "t.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc=duration=4:size=320x240:rate=10",
                    "-pix_fmt", "yuv420p", str(p)], check=True)
    return p


def stub_cosmos(monkeypatch, payload):
    text = payload if isinstance(payload, str) else "<think>hmm {not json}</think>\n```json\n" + json.dumps(payload) + "\n```"
    monkeypatch.setattr(cosmos, "call_cosmos", lambda frames: text)


def new_run(client, clip):
    r = client.post("/api/runs", files={"file": ("t.mp4", clip.read_bytes(), "video/mp4")})
    assert r.status_code == 200, r.text
    return r.json()["run_id"]


def post(client, rid, step, **kw):
    return client.post(f"/api/runs/{rid}/{step}", **kw)


def to_confirmed(client, clip, monkeypatch, zone="right_rack"):
    stub_cosmos(monkeypatch, GOOD)
    rid = new_run(client, clip)
    assert post(client, rid, "analyse").json()["state"] == "analysed"
    r = post(client, rid, "confirm", json={"fire_id": "F1", "zone": zone})
    assert r.status_code == 200 and r.json()["state"] == "confirmed"
    return rid


def test_upload_rejects_non_video(client):
    r = client.post("/api/runs", files={"file": ("x.mp4", b"not a video at all", "video/mp4")})
    assert r.status_code == 422 and "retryable" in r.json()


def test_invalid_cosmos_json_needs_review(client, clip, monkeypatch):
    stub_cosmos(monkeypatch, "I think there is a fire but no json")
    rid = new_run(client, clip)
    run = post(client, rid, "analyse").json()
    assert run["state"] == "needs_review" and run["error"]["retryable"] is True
    assert run["analysis"]["raw_text"]
    assert post(client, rid, "scene").status_code == 409
    assert post(client, rid, "run").status_code == 409
    assert post(client, rid, "confirm", json={"fire_id": "F1", "zone": "right_rack"}).status_code == 409


def test_bad_bbox_and_timestamps_needs_review(client, clip, monkeypatch):
    bad = json.loads(json.dumps(GOOD))
    bad["fire_sources"][0]["bbox_normalized"] = [0.8, 0.4, 0.6, 0.7]
    stub_cosmos(monkeypatch, bad)
    rid = new_run(client, clip)
    assert post(client, rid, "analyse").json()["state"] == "needs_review"
    bad["fire_sources"][0]["bbox_normalized"] = [0.1, 0.1, 0.2, 0.2]
    bad["fire_sources"][0]["timestamps_s"] = [99.0]
    stub_cosmos(monkeypatch, bad)
    assert post(client, rid, "analyse").json()["state"] == "needs_review"  # retry allowed from needs_review


def test_bbox_on_0_1000_grid_is_rescaled(client, clip, monkeypatch):
    grid = json.loads(json.dumps(GOOD))
    grid["fire_sources"][0]["bbox_normalized"] = [620, 400, 800, 710]
    stub_cosmos(monkeypatch, grid)
    rid = new_run(client, clip)
    run = post(client, rid, "analyse").json()
    fs = run["observations"]["fire_sources"][0]
    assert run["state"] == "analysed" and fs["bbox_normalized"] == [0.62, 0.4, 0.8, 0.71]
    assert fs["bbox_source_scale"] == "0-1000" and fs["suggested_zone"] == "right_rack"


def test_cosmos_timeout_failed_retryable_then_recovers(client, clip, monkeypatch):
    def boom(frames):
        raise cosmos.UpstreamError("timeout")
    monkeypatch.setattr(cosmos, "call_cosmos", boom)
    rid = new_run(client, clip)
    run = post(client, rid, "analyse").json()
    assert run["state"] == "failed" and run["error"]["retryable"] is True and run["error"]["stage"] == "analyse"
    stub_cosmos(monkeypatch, GOOD)
    assert post(client, rid, "analyse").json()["state"] == "analysed"


def test_confirm_validation(client, clip, monkeypatch):
    stub_cosmos(monkeypatch, GOOD)
    rid = new_run(client, clip)
    assert post(client, rid, "confirm", json={"fire_id": "F1", "zone": "right_rack"}).status_code == 409
    post(client, rid, "analyse")
    assert post(client, rid, "confirm", json={"fire_id": "F9", "zone": "right_rack"}).status_code == 422
    assert post(client, rid, "confirm", json={"fire_id": "F1", "zone": "mars"}).status_code == 422


@pytest.mark.parametrize("skill", [{"name": "teleport", "target_id": "F1"}, {"name": "aim_spray_demo", "target_id": "F7"}])
def test_invalid_plan_blocked(client, clip, monkeypatch, skill):
    rid = to_confirmed(client, clip, monkeypatch)
    monkeypatch.setattr(planner, "call_wandb", lambda *a: ({"instruction": "x", "skill": skill}, "m"))
    run = post(client, rid, "scene").json()
    assert run["state"] == "blocked" and run["error"]["stage"] == "plan"
    assert post(client, rid, "run").status_code == 409


def test_wandb_down_uses_labelled_fallback(client, clip, monkeypatch):
    rid = to_confirmed(client, clip, monkeypatch)
    def down(*a):
        raise RuntimeError("503")
    monkeypatch.setattr(planner, "call_wandb", down)
    run = post(client, rid, "scene").json()
    assert run["state"] == "scene_ready" and run["instruction"]["source"] == "fallback"
    assert run["instruction"]["text"] == "Aim the attached extinguisher at F1"


def test_behind_robot_blocked(client, clip, monkeypatch):
    rid = to_confirmed(client, clip, monkeypatch, zone="behind_robot")
    run = post(client, rid, "scene").json()
    assert run["state"] == "blocked" and "not reachable" in run["error"]["message"]
    assert post(client, rid, "run").status_code == 409


def test_happy_path_and_reset_replay(client, clip, monkeypatch):
    rid = to_confirmed(client, clip, monkeypatch)
    assert post(client, rid, "run").status_code == 409  # scene not built yet
    run = post(client, rid, "scene").json()
    assert run["state"] == "scene_ready" and run["instruction"]["source"] == "wandb"
    run = post(client, rid, "run").json()
    assert run["state"] == "completed" and run["metrics"]["success"] is True
    assert client.get(f"/api/runs/{rid}/trajectory").json()["frames"]
    assert post(client, rid, "run").status_code == 409  # must reset first
    m1 = run["metrics"]
    run = post(client, rid, "reset").json()
    assert run["state"] == "scene_ready" and run["metrics"] is None and run["scene"]
    assert client.get(f"/api/runs/{rid}/trajectory").status_code == 404
    assert post(client, rid, "run").json()["metrics"] == m1
    assert client.get(f"/api/runs/{rid}/video").status_code == 200


def test_zones_and_clips(client):
    z = client.get("/api/zones").json()
    assert z["behind_robot"]["reachable"] is False and z["right_rack"]["reachable"] is True
    assert isinstance(client.get("/api/clips").json(), list)
