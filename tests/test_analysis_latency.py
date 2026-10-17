"""Concurrency contract for analysis: overlap without changing evidence ordering."""
import contextvars
import threading

from scene2real import config, cosmos, grounding, ingest, matching, pipeline, records, yolo


def test_analysis_overlaps_reviews_and_associations_in_view_order(tmp_path, monkeypatch):
    marker = contextvars.ContextVar("analysis_test_marker", default="missing")
    marker.set("trace")
    run = {"run_id": "overlap", "state": "uploaded", "error": None, "telemetry": {},
           "clip_ref": {"view_id": "V1", "duration_s": 2, "sha256": "1"},
           "video_refs": [{"view_id": f"V{i}", "duration_s": 2, "sha256": str(i)} for i in (1, 2)]}
    monkeypatch.setattr(pipeline, "get_run", lambda _: run)
    monkeypatch.setattr(pipeline, "source_video", lambda _, vid: tmp_path / vid)
    monkeypatch.setattr(config, "RUNS_DIR", tmp_path)
    monkeypatch.setattr(config, "spatial_review_enabled", lambda: True)
    monkeypatch.setattr(records, "save", lambda _: None)
    monkeypatch.setattr(records, "archive", lambda _: None)
    monkeypatch.setattr(ingest, "extract_frames", lambda clip, duration, path: [{"path": str(clip), "t_s": .5}])
    monkeypatch.setattr(yolo, "detect", lambda clip: ([], "ok"))
    review_started, next_cosmos = threading.Event(), threading.Event()
    association_started, matching_started = threading.Event(), threading.Event()
    cosmos_order = []

    def analyse(frames, duration, sha, allow_empty=False):
        assert allow_empty
        cosmos_order.append(sha)
        if sha == "2":
            assert review_started.wait(5), "first review was not started before next Cosmos call"
            next_cosmos.set()
        fire = {"id": "F1", "bbox_normalized": [.1, .1, .2, .2]}
        return {"raw_text": f"raw {sha}", "latency_s": 1.0}, {"fire_sources": [fire], "unknowns": []}

    def review(frames, duration, obs):
        assert marker.get() == "trace"
        if frames[0]["path"].endswith("V1"):
            review_started.set()
            assert next_cosmos.wait(5), "next Cosmos call waited for review"
        return {"status": "completed", "raw_text": "review evidence"}, obs

    def cosmos_association(views, paths):
        assert marker.get() == "trace"
        association_started.set()
        assert matching_started.wait(5), "association calls were not concurrent"
        return {"status": "manual_review", "candidates": [], "error": None, "raw_text": "cosmos evidence"}

    def match(views, paths):
        assert marker.get() == "trace"
        matching_started.set()
        assert association_started.wait(5), "association calls were not concurrent"
        return {"status": "manual_review", "candidates": [], "error": None, "raw_text": "matching evidence"}

    monkeypatch.setattr(cosmos, "analyse", analyse)
    monkeypatch.setattr(grounding, "review", review)
    monkeypatch.setattr(cosmos, "propose_associations", cosmos_association)
    monkeypatch.setattr(matching, "propose", match)
    result = pipeline.analyse("overlap")
    assert result["state"] == "analysed"
    assert cosmos_order == ["1", "2"]
    assert [v["view_id"] for v in result["analysis"]["views"]] == ["V1", "V2"]
    assert [f["id"] for f in result["observations"]["fire_sources"]] == ["V1:F1", "V2:F1"]
    assert [v["analysis"]["raw_text"] for v in result["analysis"]["views"]] == ["raw 1", "raw 2"]
    assert result["analysis"]["cosmos_association"]["raw_text"] == "cosmos evidence"
    assert result["analysis"]["association"]["raw_text"] == "matching evidence"
    assert result["analysis"]["latency_s"] == result["timings_s"]["analyse"]
    assert "analyse_views" in result["timings_s"] and "analyse_association" in result["timings_s"]
