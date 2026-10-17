"""Run state machine, stage gating, persistence, telemetry."""
import json
import secrets
import shutil
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from . import config, cosmos, ingest, planner, records, yolo

CLIP_LABEL = "local upload adapter (archived to VAST S3)"
_RUNS: dict[str, dict] = {}
_LOCKS: dict[str, threading.Lock] = {}
_GLOBAL = threading.Lock()

DOWNSTREAM_OF_ANALYSE = ("observations", "confirmed_target", "scene", "instruction", "skill", "metrics")


class PipelineError(Exception):
    def __init__(self, status, detail, retryable=False):
        super().__init__(detail)
        self.status, self.detail, self.retryable = status, detail, retryable


def _lock(run_id):
    with _GLOBAL:
        return _LOCKS.setdefault(run_id, threading.Lock())


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _commit(run):
    run["telemetry"]["weave"] = config.TELEMETRY["weave"]
    records.save(run)
    return run


def get_run(run_id):
    if "/" in run_id or ".." in run_id:
        raise PipelineError(404, "run not found")
    run = _RUNS.get(run_id) or records.load(run_id)
    if run is None:
        raise PipelineError(404, "run not found")
    _RUNS[run_id] = run
    return run


def _fail(run, stage, message, retryable, state="failed"):
    run["state"] = state
    run["error"] = {"stage": stage, "message": message, "retryable": retryable}


# ---------- clips ----------

def list_clips():
    out = []
    meta = {}
    mp = config.CLIPS_DIR / "clips.json"
    if mp.exists():
        try:
            meta = json.loads(mp.read_text())
        except ValueError:
            meta = {}
    if isinstance(meta, list):
        meta = {m.get("filename") or m.get("clip_id"): m for m in meta if isinstance(m, dict)}
    for p in sorted(config.CLIPS_DIR.glob("*.mp4")):
        m = meta.get(p.name) or meta.get(p.stem) or {}
        if isinstance(m, str):
            m = {"label": m}
        try:
            dur = round(ingest.probe(p)["duration_s"], 2)
        except ingest.IngestError:
            continue
        out.append({"clip_id": p.stem, "label": m.get("label") or p.stem, "filename": p.name, "duration_s": dur})
    return out


def _new_run(src: Path, filename, kind, label):
    run_id = f"r_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{secrets.token_hex(2)}"
    d = records.run_dir(run_id)
    d.mkdir(parents=True, exist_ok=True)
    dst = d / "clip.mp4"
    try:
        if src.resolve() != dst.resolve():
            shutil.copyfile(src, dst)
        info = ingest.validate_clip(dst)
    except ingest.IngestError as e:
        shutil.rmtree(d, ignore_errors=True)
        raise PipelineError(422, str(e), False)
    run = {
        "run_id": run_id, "created_at": _now(), "state": "uploaded", "error": None,
        "clip_ref": {"kind": kind, "filename": filename, "sha256": info["sha256"], "duration_s": info["duration_s"],
                     "local_path": f"runs/{run_id}/clip.mp4", "s3_uri": None, "label": label or CLIP_LABEL},
        "model_id": cosmos.MODEL_ID, "prompt_id": cosmos.PROMPT_ID, "analysis": None, "observations": None,
        "confirmed_target": None, "scene": None, "instruction": None, "skill": None, "metrics": None,
        "timings_s": {}, "telemetry": {"weave": config.TELEMETRY["weave"], "vast": "pending"},
    }
    records.save(run)
    records.archive(run, with_clip=True)
    _RUNS[run_id] = run
    return run


def create_from_upload(tmp_path: Path, filename):
    return _new_run(tmp_path, filename or "upload.mp4", "upload", CLIP_LABEL)


def create_from_clip(clip_id):
    for c in list_clips():
        if c["clip_id"] == clip_id:
            return _new_run(config.CLIPS_DIR / c["filename"], c["filename"], "preloaded", c["label"])
    raise PipelineError(404, f"unknown clip_id {clip_id!r}")


# ---------- stages ----------

def analyse(run_id):
    run = get_run(run_id)
    with _lock(run_id):
        err = run.get("error") or {}
        ok = run["state"] in ("uploaded", "analysed", "needs_review") or (
            run["state"] == "failed" and err.get("stage") == "analyse")
        if not ok:
            raise PipelineError(409, f"Cannot analyse in state {run['state']!r}")
        for k in DOWNSTREAM_OF_ANALYSE:
            run[k] = None
        run["error"], run["timings_s"] = None, {}
        run["analysis"] = None
        clip = records.run_dir(run_id) / "clip.mp4"
        t0 = time.time()
        try:
            frames = ingest.extract_frames(clip, run["clip_ref"]["duration_s"], records.run_dir(run_id) / "frames")
        except ingest.IngestError as e:
            _fail(run, "analyse", str(e), True)
            return _commit(run)
        with ThreadPoolExecutor(1) as ex:
            yfut = ex.submit(yolo.detect, clip)
            try:
                analysis, obs = cosmos.analyse(frames, run["clip_ref"]["duration_s"], run["clip_ref"]["sha256"])
                outcome = None
            except cosmos.UpstreamError as e:
                analysis, obs, outcome = None, None, ("failed", str(e))
            except cosmos.InvalidOutput as e:
                analysis, obs, outcome = getattr(e, "analysis", None), None, ("needs_review", str(e))
            objects, ynote = yfut.result()
        run["timings_s"]["analyse"] = round(time.time() - t0, 2)
        if analysis:
            analysis["yolo"] = ynote
            run["analysis"] = analysis
        if outcome:
            kind, msg = outcome
            _fail(run, "analyse", msg, True, state=kind)
            return _commit(run)
        obs["objects"] = objects
        run["observations"] = obs
        run["state"] = "analysed"
        _commit(run)
        records.archive(run)
        return run


def confirm(run_id, fire_id, zone):
    from . import scene
    run = get_run(run_id)
    with _lock(run_id):
        if run["state"] not in ("analysed", "confirmed", "scene_ready", "blocked", "completed"):
            raise PipelineError(409, f"Cannot confirm in state {run['state']!r}")
        fs = {f["id"]: f for f in run["observations"]["fire_sources"]}
        if fire_id not in fs:
            raise PipelineError(422, f"Unknown fire_id {fire_id!r}; valid: {sorted(fs)}")
        if zone not in scene.ZONES:
            raise PipelineError(422, f"Unknown zone {zone!r}; valid: {sorted(scene.ZONES)}")
        for k in ("scene", "instruction", "skill", "metrics"):
            run[k] = None
        run["timings_s"] = {k: v for k, v in run["timings_s"].items() if k == "analyse"}
        run["error"] = None
        run["confirmed_target"] = {
            "fire_id": fire_id, "zone": zone, "image_bbox_normalized": fs[fire_id]["bbox_normalized"],
            "template_position_m": list(scene.ZONES[zone]["anchor"]),
            "position_provenance": "template-assumed (wh_aisle_v1 zone anchor)"}
        run["state"] = "confirmed"
        return _commit(run)


def _scene_obj(run):
    """Sim-facing scene dict: deterministic rebuild from observations + confirmed target (includes mjcf, fires...)."""
    from . import scene as scene_mod
    ct = run["confirmed_target"]
    return scene_mod.build_scene(run["observations"]["fire_sources"], {ct["fire_id"]: ct["zone"]}, ct["fire_id"])


def build_scene(run_id):
    from . import scene as scene_mod
    run = get_run(run_id)
    with _lock(run_id):
        err = run.get("error") or {}
        ok = run["state"] in ("confirmed", "blocked") or (
            run["state"] == "failed" and err.get("stage") in ("scene", "plan"))
        if not ok or not run.get("confirmed_target"):
            raise PipelineError(409, f"Cannot build scene in state {run['state']!r}")
        ct = run["confirmed_target"]
        fid, zone = ct["fire_id"], ct["zone"]
        run["error"], run["instruction"], run["skill"] = None, None, None
        t0 = time.time()
        try:
            built = scene_mod.build_scene(run["observations"]["fire_sources"], {fid: zone}, fid)
        except ValueError as e:
            _fail(run, "scene", str(e), False, state="blocked")
            return _commit(run)
        d = records.run_dir(run_id)
        (d / "scene.xml").write_text(built["mjcf"])
        run["scene"] = {"template_id": built["template_id"], "source_zone_mapping": built["source_zone_mapping"],
                        "placements": built["placements"], "target_pos": built["target_pos"],
                        "mjcf_path": f"runs/{run_id}/scene.xml", "settings": built["settings"]}
        run["timings_s"]["scene"] = round(time.time() - t0, 2)
        ok_reach, why = scene_mod.check_reachable(built, fid)
        if not ok_reach:
            _fail(run, "scene", f"Execution blocked: target {fid} in zone '{zone}' is not reachable ({why})",
                  False, state="blocked")
            return _commit(run)
        desc = next((f["description"] for f in run["observations"]["fire_sources"] if f["id"] == fid), "")
        ins, skill = planner.make_plan(fid, zone, desc)
        run["instruction"] = ins
        run["timings_s"]["plan"] = ins["latency_s"]
        try:
            run["skill"] = planner.validate_plan(skill, fid, built)
        except planner.PlanInvalid as e:
            _fail(run, "plan", str(e), True, state="blocked")
            return _commit(run)
        run["state"] = "scene_ready"
        _commit(run)
        records.archive(run, extra_files=("scene.xml",))
        return run


def run_sim(run_id):
    from . import sim
    run = get_run(run_id)
    with _lock(run_id):
        err = run.get("error") or {}
        ok = run["state"] == "scene_ready" or (run["state"] == "failed" and err.get("stage") == "run" and run.get("skill"))
        if not ok:
            raise PipelineError(409, f"Cannot run in state {run['state']!r}")
        run["error"] = None
        t0 = time.time()
        try:
            metrics, traj = sim.simulate(_scene_obj(run), run["skill"])
        except ValueError as e:
            _fail(run, "run", str(e), False)
            return _commit(run)
        except Exception as e:  # noqa: BLE001
            _fail(run, "run", f"Simulation error: {type(e).__name__}: {e}", True)
            return _commit(run)
        (records.run_dir(run_id) / "trajectory.json").write_text(json.dumps(traj))
        run["metrics"] = metrics
        run["timings_s"]["run"] = round(time.time() - t0, 2)
        run["state"] = "completed"
        _commit(run)
        records.archive(run, extra_files=("trajectory.json",))
        return run


def reset(run_id):
    run = get_run(run_id)
    with _lock(run_id):
        err = run.get("error") or {}
        ok = run["state"] in ("completed", "scene_ready") or (
            run["state"] == "failed" and err.get("stage") == "run" and run.get("skill"))
        if not ok:
            raise PipelineError(409, f"Cannot reset in state {run['state']!r}")
        (records.run_dir(run_id) / "trajectory.json").unlink(missing_ok=True)
        run["metrics"], run["error"], run["state"] = None, None, "scene_ready"
        run["timings_s"].pop("run", None)
        return _commit(run)


def trajectory(run_id):
    get_run(run_id)
    p = records.run_dir(run_id) / "trajectory.json"
    if not p.exists():
        raise PipelineError(404, "no trajectory yet")
    return p
