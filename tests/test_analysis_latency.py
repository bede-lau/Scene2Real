"""Concurrency contract for analysis: overlap without changing evidence ordering."""
import contextvars
import threading

from scene2real import config, cosmos, grounding, ingest, matching, pipeline, records, yolo


def test_analysis_overlaps_reviews_and_associations_in_view_order(tmp_path, monkeypatch):
    marker = contextvars.ContextVar("analysis_test_marker", default="missing")
    marker.set("trace")
    run = {"run_id": "overlap", "state": "uploaded", "error": None, "telemetry": {},
           "clip_ref": {"view_id": "V1", "duration_s": 5, "sha256": "1"},
           "video_refs": [{"view_id": "V1", "duration_s": 5, "sha256": "1"},
                          {"view_id": "V2", "duration_s": 4, "sha256": "2"}]}
    monkeypatch.setattr(pipeline, "get_run", lambda _: run)
    monkeypatch.setattr(pipeline, "source_video", lambda _, vid: tmp_path / vid)
    monkeypatch.setattr(config, "RUNS_DIR", tmp_path)
    monkeypatch.setattr(config, "spatial_review_enabled", lambda: True)
    monkeypatch.setattr(records, "save", lambda _: None)
    monkeypatch.setattr(records, "archive", lambda _: None)
    monkeypatch.setattr(ingest, "extract_frames", lambda clip, duration, path: [{"path": str(clip), "t_s": .5}])
    monkeypatch.setattr(yolo, "detect", lambda clip: ([], "ok"))
    review_started, next_cosmos, both_cosmos = threading.Event(), threading.Event(), threading.Event()
    association_started, matching_started = threading.Event(), threading.Event()
    cosmos_order = []
    cosmos_lock = threading.Lock()
    active_cosmos = 0
    max_active_cosmos = 0

    def analyse(frames, duration, sha, allow_empty=False):
        nonlocal active_cosmos, max_active_cosmos
        assert allow_empty
        assert duration == {"1": 5, "2": 4}[sha]
        with cosmos_lock:
            cosmos_order.append(sha)
            active_cosmos += 1
            max_active_cosmos = max(max_active_cosmos, active_cosmos)
            if active_cosmos == 2:
                both_cosmos.set()
        try:
            if sha == "1":
                assert both_cosmos.wait(5), "independent Cosmos requests were not concurrent"
            if sha == "2":
                assert review_started.wait(5), "first review was not started while another Cosmos request was pending"
                next_cosmos.set()
            fire = {"id": "F1", "bbox_normalized": [.1, .1, .2, .2]}
            return {"raw_text": f"raw {sha}", "latency_s": 1.0}, {"fire_sources": [fire], "unknowns": []}
        finally:
            with cosmos_lock:
                active_cosmos -= 1

    def review(frames, duration, obs):
        assert marker.get() == "trace"
        assert duration == {"V1": 5, "V2": 4}[frames[0]["path"].rsplit("/", 1)[-1]]
        if frames[0]["path"].endswith("V1"):
            review_started.set()
            assert next_cosmos.wait(5), "second Cosmos request did not complete alongside review"
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
    assert sorted(cosmos_order) == ["1", "2"]
    assert max_active_cosmos == 2
    assert [v["view_id"] for v in result["analysis"]["views"]] == ["V1", "V2"]
    assert [f["id"] for f in result["observations"]["fire_sources"]] == ["V1:F1", "V2:F1"]
    assert [v["analysis"]["raw_text"] for v in result["analysis"]["views"]] == ["raw 1", "raw 2"]
    assert result["analysis"]["cosmos_association"]["raw_text"] == "cosmos evidence"
    assert result["analysis"]["association"]["raw_text"] == "matching evidence"
    assert result["analysis"]["latency_s"] == result["timings_s"]["analyse"]
    assert "analyse_views" in result["timings_s"] and "analyse_association" in result["timings_s"]
