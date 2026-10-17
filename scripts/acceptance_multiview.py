"""Live Cosmos -> reviewed associations -> Astra -> mobile response and recording.

Create a fresh incident with --clip-ids and an operator-reviewed --confirmation JSON,
or verify and repeat a completed browser journey with --run-id. Expected counts are
used only after inference for QA; they are never sent to Cosmos or Astra.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scene2real import ingest  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--base", default="http://127.0.0.1:8090")
    start = ap.add_mutually_exclusive_group(required=True)
    start.add_argument("--run-id")
    start.add_argument("--clip-ids", nargs="+", help="One to three preloaded view IDs")
    ap.add_argument("--confirmation", type=Path, help="Operator-reviewed targets/exclusions JSON; never fixture truth")
    ap.add_argument("--expected-targets", type=int, required=True, help="Evaluation assertion only")
    ap.add_argument("--repeats", type=int, default=3, help="Additional reset/run cycles")
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    base = a.base.rstrip("/")
    checks = []
    session = requests.Session()

    def request(method, path, **kwargs):
        response = session.request(method, base + path, timeout=600, **kwargs)
        response.raise_for_status()
        return response

    def check(name, passed, **details):
        checks.append({"check": name, "pass": bool(passed), **details})
        print(("PASS " if passed else "FAIL ") + name, flush=True)
        if not passed:
            raise AssertionError(f"{name}: {details}")

    report = {"environment": "local live providers", "checks": checks,
              "scope": "Mechanical pipeline checks after operator confirmation. Target counts are counts of confirmed groups, not proof of visual localization or cross-camera identity.",
              "visual_localization_verified": False, "physical_fire_coverage_verified": False}
    try:
        if a.clip_ids:
            run = request("POST", "/api/runs", json={"clip_ids": a.clip_ids}).json()
            rid = run["run_id"]
            run = request("POST", f"/api/runs/{rid}/analyse").json()
            a.out.parent.mkdir(parents=True, exist_ok=True)
            a.out.with_suffix(".analysis.json").write_text(json.dumps(run, indent=2))
            check("all views analysed", run["state"] == "analysed", state=run["state"], error=run.get("error"))
            if not a.confirmation:
                raise ValueError("Inspect the saved analysis and supply operator-reviewed --confirmation JSON")
            run = request("POST", f"/api/runs/{rid}/confirm", json=json.loads(a.confirmation.read_text())).json()
            check("physical targets confirmed", run["state"] == "confirmed")
            run = request("POST", f"/api/runs/{rid}/scene").json()
            check("Astra scene ready", run["state"] == "scene_ready", error=run.get("error"))
            run = request("POST", f"/api/runs/{rid}/run").json()
        else:
            rid = a.run_id
            run = request("GET", f"/api/runs/{rid}").json()
        report["run_id"] = rid
        check("completed mobile response", run["state"] == "completed" and run.get("response_mode") == "mobile", error=run.get("error"))
        refs, views = run.get("video_refs", []), run.get("analysis", {}).get("views", [])
        check("one to three source views retained", 1 <= len(refs) <= 3 and len(refs) == len(views))
        check("uncached real Cosmos and YOLO", all(v["state"] == "analysed" and v["analysis"]["raw_text"]
              and v["analysis"]["cached"] is False and v["analysis"].get("yolo") == "ok" for v in views))
        check("uncalibrated depth remains unknown", all(v["observations"]["depth_m"] is None for v in views))
        check("operator-confirmed target count", len(run.get("confirmed_targets", [])) == a.expected_targets)
        ins = run.get("instruction") or {}
        check("real Astra instruction and scene settings", ins.get("source") == "openai"
              and ins.get("model_id", "").startswith("gpt-6-astra") and ins.get("raw_plan")
              and run["scene"]["settings"] == ins["raw_plan"]["scene_settings"])
        reference_metrics, reference_trajectory = None, None
        durations = []
        for index in range(a.repeats + 1):
            if index:
                reset = request("POST", f"/api/runs/{rid}/reset").json()
                check(f"reset {index} clears outcomes", reset["state"] == "scene_ready" and reset["metrics"] is None
                      and reset["simulation_video"] is None)
                check(f"reset {index} removes recording", session.get(base + f"/api/runs/{rid}/simulation-video").status_code == 404)
                run = request("POST", f"/api/runs/{rid}/run").json()
            m = run.get("metrics") or {}
            check(f"run {index + 1}: all fires suppressed without collisions", run["state"] == "completed"
                  and m.get("success") is True and m.get("suppressed_count") == a.expected_targets
                  and m.get("target_count") == a.expected_targets and m.get("unintended_collision_count") == 0
                  and all(t["suppressed"] and t["best_valid_exposure_s"] >= 2.0 for t in m.get("targets", [])))
            trajectory = request("GET", f"/api/runs/{rid}/trajectory").json()
            digest = hashlib.sha256(json.dumps(trajectory, sort_keys=True).encode()).hexdigest()
            check(f"run {index + 1}: station departure and articulated walking", m.get("started_at_charging_station")
                  and m.get("distance_travelled_m", 0) > 0 and "walking" in trajectory["phases"]
                  and trajectory["base_positions"][0] == run["scene"]["station_pose"])
            check(f"run {index + 1}: every fire has a suppression event", all(f.get("suppressed_frame") is not None
                  and 0 < f["suppressed_frame"] < len(trajectory["frames"]) for f in trajectory["fx"]["fires"]))
            recording = request("GET", f"/api/runs/{rid}/simulation-video").content
            a.out.parent.mkdir(parents=True, exist_ok=True)
            movie = a.out.with_suffix(".mp4")
            movie.write_bytes(recording)
            info = ingest.probe(movie)
            check(f"run {index + 1}: decodable recording", info["duration_s"] > 1 and len(recording) > 1000)
            durations.append(info["duration_s"])
            if reference_metrics is None:
                reference_metrics, reference_trajectory = m, digest
            else:
                check(f"run {index + 1}: deterministic measured outcome and poses", m == reference_metrics and digest == reference_trajectory)
        persisted = request("GET", f"/api/runs/{rid}").json()
        check("saved target/evidence/plan/outcome agreement", persisted == run)
        report.update(state=run["state"], metrics=run["metrics"], instruction=run["instruction"],
                      recording=run["simulation_video"], source_hashes=[v["sha256"] for v in refs],
                      trajectory_sha256=reference_trajectory, repeated_recording_durations_s=durations,
                      all_passed=True)
    except Exception as exc:
        report.update(all_passed=False, failure=f"{type(exc).__name__}: {exc}")
        raise
    finally:
        a.out.parent.mkdir(parents=True, exist_ok=True)
        a.out.write_text(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
