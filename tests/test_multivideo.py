import json
import subprocess

import pytest
from fastapi.testclient import TestClient

from scene2real import config, cosmos, ingest, pipeline, records, yolo
from scene2real.app import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "RUNS_DIR", tmp_path / "runs")
    monkeypatch.setattr(config, "CLIPS_DIR", tmp_path / "clips")
    config.CLIPS_DIR.mkdir()
    pipeline._RUNS.clear()
    monkeypatch.setattr(records, "archive", lambda *a, **k: None)
    monkeypatch.setattr(yolo, "detect", lambda path: ([], "stub"))
    return TestClient(app)


@pytest.fixture(scope="module")
def video(tmp_path_factory):
    p = tmp_path_factory.mktemp("multi") / "source.mp4"
    subprocess.run([ingest.media_tool("ffmpeg"), "-v", "error", "-f", "lavfi", "-i", "testsrc=duration=2:size=320x240:rate=10", "-pix_fmt", "yuv420p", str(p)], check=True)
    return p.read_bytes()


def fire(fid="F1"):
    return {"id": fid, "timestamps_s": [0.5], "bbox_normalized": [0.1, 0.1, 0.4, 0.5], "description": "flames beside boxes"}


def setup_analysis(monkeypatch, payloads):
    it = iter(payloads)
    def analyse(frames, duration, sha, allow_empty=False):
        value = next(it)
        if isinstance(value, Exception):
            raise value
        obs = cosmos.validate({"fire_sources": value}, duration, allow_empty=allow_empty)
        obs["objects"] = []
        return {"raw_text": json.dumps(value)}, obs
    monkeypatch.setattr(cosmos, "analyse", analyse)
    monkeypatch.setattr(cosmos, "propose_associations", lambda views, paths: {"status": "manual_review", "candidates": [], "error": None})


def create(client, video, n=2):
    return client.post("/api/runs", files=[("files", (f"view{i}.mp4", video, "video/mp4")) for i in range(n)])


def test_atomic_ingest_and_aliases(client, video):
    r = create(client, video, 3)
    assert r.status_code == 200
    run = r.json()
    assert [v["view_id"] for v in run["video_refs"]] == ["V1", "V2", "V3"]
    rid = run["run_id"]
    assert client.get(f"/api/runs/{rid}/video").content == client.get(f"/api/runs/{rid}/video/V1").content
    assert client.get(f"/api/runs/{rid}/video/V3").status_code == 200
    assert client.get(f"/api/runs/{rid}/video/V4").status_code == 404
    before = set(config.RUNS_DIR.iterdir())
    r = client.post("/api/runs", files=[("files", ("ok.mp4", video, "video/mp4")), ("files", ("bad.mp4", b"bad", "video/mp4"))])
    assert r.status_code == 422 and set(config.RUNS_DIR.iterdir()) == before
    assert create(client, video, 4).status_code == 422


def test_multiview_empty_view_invalid_view_and_retry(client, video, monkeypatch):
    rid = create(client, video).json()["run_id"]
    setup_analysis(monkeypatch, [[], [fire()]])
    run = client.post(f"/api/runs/{rid}/analyse").json()
    assert run["state"] == "analysed"
    assert run["analysis"]["views"][0]["observations"]["fire_sources"] == []
    assert run["observations"]["fire_sources"][0]["id"] == "V2:F1"
    setup_analysis(monkeypatch, [[fire()], cosmos.InvalidOutput("bad output")])
    run = client.post(f"/api/runs/{rid}/analyse").json()
    assert run["state"] == "needs_review" and run["observations"] is None
    assert client.post(f"/api/runs/{rid}/confirm", json={"targets": [], "excluded": []}).status_code == 409
    setup_analysis(monkeypatch, [[], []])
    assert client.post(f"/api/runs/{rid}/analyse").json()["state"] == "needs_review"
    setup_analysis(monkeypatch, [[fire()], [fire()]])
    assert client.post(f"/api/runs/{rid}/analyse").json()["state"] == "analysed"


def test_confirmation_membership_and_slots(client, video, monkeypatch):
    from scene2real import mobile
    rid = create(client, video).json()["run_id"]
    setup_analysis(monkeypatch, [[fire(), fire("F2")], [fire()]])
    client.post(f"/api/runs/{rid}/analyse")
    zone = next(z for z, slots in mobile.SLOTS.items() if len(slots) >= 2)
    endpoint = f"/api/runs/{rid}/confirm"
    def post(targets, excluded=[]):
        return client.post(endpoint, json={"targets": targets, "excluded": excluded})
    good = [{"members": ["V1:F1", "V2:F1"], "zone": zone, "slot": 0}, {"members": ["V1:F2"], "zone": zone, "slot": 1}]
    assert post(good[:1]).status_code == 422
    assert post([{"members": ["V1:F1", "V1:F2"], "zone": zone, "slot": 0}], [{"id": "V2:F1", "reason": "duplicate"}]).status_code == 422
    assert post([good[0], {**good[1], "slot": 0}]).status_code == 422
    assert post([good[0]], [{"id": "V1:F2", "reason": ""}]).status_code == 422
    assert post([{**good[0], "members": ["V1:F1", "V9:F1"]}], [{"id": "V1:F2", "reason": "mistake"}]).status_code == 422
    run = post(good).json()
    assert run["state"] == "confirmed" and run["response_mode"] == "mobile"
    assert run["observations"]["evidence_warnings"][0]["members"] == ["V1:F1", "V1:F2"]
    assert [t["fire_id"] for t in run["confirmed_targets"]] == ["T1", "T2"]
    assert run["confirmed_target"] == run["confirmed_targets"][0]
    assert run["confirmed_targets"][0]["position_provenance"].startswith("template-assumed")


def test_association_is_validated_and_contains_only_visual_evidence(tmp_path, monkeypatch):
    frame = tmp_path / "frame.jpg"
    frame.write_bytes(b"jpeg")
    views = [{"view_id": "V1", "observations": {"fire_sources": [{**fire(), "id": "V1:F1", "view_id": "V1", "source_id": "F1", "secret_truth": "not for model"}]}},
             {"view_id": "V2", "observations": {"fire_sources": [{**fire(), "id": "V2:F1", "view_id": "V2", "source_id": "F1"}]}}]
    monkeypatch.setattr(config, "get", lambda name: "test-token")
    class Response:
        def raise_for_status(self):
            pass
        def json(self):
            return {"choices": [{"message": {"content": json.dumps({"association_candidates": [{"members": ["V1:F1", "V2:F1"], "reason": "Similar pallets"}]})}}]}
    def request(*args, **kwargs):
        assert "secret_truth" not in json.dumps(kwargs["json"])
        assert sum(c["type"] == "image_url" for c in kwargs["json"]["messages"][0]["content"]) == 2
        return Response()
    monkeypatch.setattr(cosmos.requests, "post", request)
    assert cosmos.propose_associations(views, [frame, frame])["candidates"][0]["members"] == ["V1:F1", "V2:F1"]
    class BadResponse(Response):
        def json(self):
            return {"choices": [{"message": {"content": '{"association_candidates":[{"members":["V1:F1","V1:F1"],"reason":"x"}]}'}}]}
    monkeypatch.setattr(cosmos.requests, "post", lambda *a, **kw: BadResponse())
    failed = cosmos.propose_associations(views, [frame, frame])
    assert failed["status"] == "manual_review" and failed["candidates"] == []
    assert "invalid association membership" in failed["error"] and failed["raw_text"]


def test_mixed_preloaded_and_uploaded_sources(client, video):
    (config.CLIPS_DIR / "demo.mp4").write_bytes(video)
    response = client.post("/api/runs", data={"clip_ids": '["demo"]'}, files=[("files", ("upload.mp4", video, "video/mp4"))])
    assert response.status_code == 200
    assert [v["kind"] for v in response.json()["video_refs"]] == ["preloaded", "upload"]
    assert client.post("/api/runs", json={"clip_id": "demo", "clip_ids": ["demo"]}).status_code == 422
    assert client.post("/api/runs", data={"clip_ids": '["demo"]'}, files=[("file", ("old.mp4", video, "video/mp4"))]).status_code == 422


def test_mobile_pipeline_export_failure_retry_and_reset(client, video, monkeypatch):
    from scene2real import mobile, planner, rendering
    rid = create(client, video).json()["run_id"]
    setup_analysis(monkeypatch, [[fire()], [fire()]])
    client.post(f"/api/runs/{rid}/analyse")
    zone = next(iter(mobile.SLOTS))
    result = client.post(f"/api/runs/{rid}/confirm", json={"targets": [{"members": ["V1:F1", "V2:F1"], "zone": zone, "slot": 0}], "excluded": []})
    assert result.status_code == 200
    settings = {"template_id": "wh_mobile_v1", "route_profile": "aisle_safe", "walk_speed_m_s": 1.0, "spray_profile": "water_demo", "spray_duration_s": 3.0}
    monkeypatch.setattr(planner, "make_mobile_plan", lambda targets, evidence: ({"source": "openai", "model_id": "gpt-6-astra", "latency_s": 1}, {"name": "mobile_suppress_demo", "target_ids": ["T1"]}, settings))
    assert client.post(f"/api/runs/{rid}/scene").json()["state"] == "scene_ready"
    def fail(*args):
        raise RuntimeError("encoder unavailable")
    monkeypatch.setattr(rendering, "export_video", fail)
    result = client.post(f"/api/runs/{rid}/run").json()
    assert result["state"] == "failed" and result["error"]["stage"] == "export" and result["error"]["retryable"]
    assert client.get(f"/api/runs/{rid}/simulation-video").status_code == 404
    def export(scene, traj, dest):
        dest.write_bytes(b"sample")
        return {"filename": "simulation.mp4"}
    monkeypatch.setattr(rendering, "export_video", export)
    run = client.post(f"/api/runs/{rid}/run").json()
    assert run["state"] == "completed" and run["metrics"]["target_count"] == 1
    assert client.get(f"/api/runs/{rid}/simulation-video").content == b"sample"
    run = client.post(f"/api/runs/{rid}/reset").json()
    assert run["state"] == "scene_ready" and run["scene"] and run["instruction"] and run["metrics"] is None
    assert client.get(f"/api/runs/{rid}/simulation-video").status_code == 404
    assert client.get(f"/api/runs/{rid}/trajectory").status_code == 404


def test_multiview_rejects_legacy_confirmation_without_changing_run(client, video, monkeypatch):
    from scene2real import mobile, planner
    rid = create(client, video).json()["run_id"]
    setup_analysis(monkeypatch, [[fire()], [fire()]])
    client.post(f"/api/runs/{rid}/analyse")
    url = f"/api/runs/{rid}"
    before = client.get(url).json()
    legacy = {"fire_id": "V1:F1", "zone": "right_rack"}
    response = client.post(url + "/confirm", json=legacy)
    assert response.status_code == 422 and "targets" in response.json()["detail"]
    assert client.get(url).json() == before
    zone = next(iter(mobile.SLOTS))
    assert client.post(url + "/confirm", json={"targets": [{"members": ["V1:F1", "V2:F1"], "zone": zone, "slot": 0}], "excluded": []}).status_code == 200
    settings = {"template_id": "wh_mobile_v1", "route_profile": "aisle_safe", "walk_speed_m_s": 1.0, "spray_profile": "water_demo", "spray_duration_s": 3.0}
    monkeypatch.setattr(planner, "make_mobile_plan", lambda targets, evidence: ({"source": "openai", "model_id": "gpt-6-astra", "latency_s": 1}, {"name": "mobile_suppress_demo", "target_ids": ["T1"]}, settings))
    assert client.post(url + "/scene").json()["state"] == "scene_ready"
    before = client.get(url).json()
    scene_xml = (config.RUNS_DIR / rid / "scene.xml").read_bytes()
    response = client.post(url + "/confirm", json=legacy)
    assert response.status_code == 422 and "targets" in response.json()["detail"]
    assert client.get(url).json() == before
    assert before["response_mode"] == "mobile" and before["instruction"]["source"] == "openai"
    assert (config.RUNS_DIR / rid / "scene.xml").read_bytes() == scene_xml


def test_association_preserves_reasoning_and_manual_review(tmp_path, monkeypatch):
    frame = tmp_path / "frame.jpg"
    frame.write_bytes(b"jpeg")
    views = [{"view_id": "V1", "observations": {"fire_sources": []}}]
    monkeypatch.setattr(config, "get", lambda name: "test-token")
    class Response:
        text = "raw http response"
        def raise_for_status(self):
            pass
        def json(self):
            return {"model": "served-cosmos", "choices": [{"message": {"content": "", "reasoning_content": '{"association_candidates":[]}'}}]}
    monkeypatch.setattr(cosmos.requests, "post", lambda *args, **kwargs: Response())
    association = cosmos.propose_associations(views, [frame])
    assert association["status"] == "manual_review" and association["error"] is None
    assert association["reasoning_content"] == '{"association_candidates":[]}'
    assert association["raw_text"] and association["model_id"] == "served-cosmos"
    assert association["prompt_id"] == "cosmos_association_v2" and "Evidence:" in association["prompt"]
    class Bad(Response):
        def json(self):
            raise ValueError("malformed response")
    monkeypatch.setattr(cosmos.requests, "post", lambda *args, **kwargs: Bad())
    failed = cosmos.propose_associations(views, [frame])
    assert failed["status"] == "manual_review" and failed["raw_text"] == "raw http response"
    assert "malformed response" in failed["error"] and failed["prompt"]


def test_association_accepts_fenced_array_without_weakening_membership(tmp_path, monkeypatch):
    frame = tmp_path / "frame.jpg"
    frame.write_bytes(b"jpeg")
    views = [{"view_id": v, "observations": {"fire_sources": [{**fire(), "id": v + ":F1", "view_id": v}]}} for v in ("V1", "V2")]
    monkeypatch.setattr(config, "get", lambda name: "test-token")
    class Response:
        def raise_for_status(self):
            pass
        def json(self):
            return {"choices": [{"message": {"content": '```json\n[{"members":["V1:F1","V2:F1"],"reason":"Same pallet"}]\n```'}}]}
    monkeypatch.setattr(cosmos.requests, "post", lambda *args, **kwargs: Response())
    result = cosmos.propose_associations(views, [frame, frame])
    assert result["status"] == "proposed" and result["candidates"][0]["members"] == ["V1:F1", "V2:F1"]


def test_multiview_uncertainty_keeps_view_provenance(client, video, monkeypatch):
    rid = create(client, video).json()["run_id"]
    values = iter([
        {"fire_sources": [], "unknowns": ["V1 visibility"], "cause": "electrical", "scale": "large"},
        {"fire_sources": [fire()], "unknowns": ["occlusion", "fire identity"], "cause": "unknown ignition", "scale": "small"},
    ])
    def analyse(frames, duration, sha, allow_empty=False):
        raw = next(values)
        return {"raw_text": json.dumps(raw)}, cosmos.validate(raw, duration, allow_empty=allow_empty)
    monkeypatch.setattr(cosmos, "analyse", analyse)
    monkeypatch.setattr(cosmos, "propose_associations", lambda *a: {"status": "manual_review", "candidates": [], "error": None})
    run = client.post(f"/api/runs/{rid}/analyse").json()
    obs = run["observations"]
    assert run["state"] == "analysed" and obs["fire_sources"][0]["id"] == "V2:F1"
    assert {"occlusion", "fire identity", "V1 visibility"}.issubset(obs["unknowns"])
    assert next(v for v in obs["view_unknowns"] if v["view_id"] == "V2")["unknowns"][:2] == ["occlusion", "fire identity"]
    assert obs["cause"] is None and obs["scale"] is None and obs["depth_m"] is None
    assert {"cause", "scale", "depth"}.issubset(obs["unknowns"])
    assert run["analysis"]["views"][1]["observations"]["unknowns"][:2] == ["occlusion", "fire identity"]
