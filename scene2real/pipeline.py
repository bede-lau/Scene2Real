"""Run state machine, stage gating, persistence, telemetry."""
import hashlib
import json
import secrets
import shutil
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from . import config, cosmos, grounding, ingest, matching, observability, planner, records, yolo

CLIP_LABEL = "local upload adapter (archived to VAST S3)"
_RUNS: dict[str, dict] = {}
_LOCKS: dict[str, threading.Lock] = {}
_GLOBAL = threading.Lock()

DOWNSTREAM_OF_ANALYSE = ("observations", "confirmed_target", "confirmed_targets", "response_mode", "scene", "instruction", "skill", "metrics", "simulation_video", "simulation_identity")


class PipelineError(Exception):
    def __init__(self, status, detail, retryable=False):
        super().__init__(detail)
        self.status, self.detail, self.retryable = status, detail, retryable


def _lock(run_id):
    with _GLOBAL:
        return _LOCKS.setdefault(run_id, threading.Lock())


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _event(run, stage, *, provenance="deterministic", **attrs):
    return observability.emit(stage, run_id=run["run_id"], parent_run_id=run.get("parent_run_id"),
                              provenance=provenance, simulation_identity=run.get("simulation_identity"),
                              scene_revision=attrs.pop("scene_revision", observability.digest(run["scene"]) if run.get("scene") else None), **attrs)


def _identity(built, mode):
    sources = ("mobile.py", "robot_profile.py") if mode == "mobile" else ("scene.py", "sim.py")
    source_assets = [observability.artifact(Path(__file__).parent / name) for name in sources]
    return {"mode": mode, "model_id": "r1_reduced_control_v1" if mode == "mobile" else "legacy_fixed_base_v1",
            "source_asset_sha256": observability.digest([{ "path": Path(asset["path"]).name, "sha256": asset.get("sha256")} for asset in source_assets]),
            "source_assets": source_assets,
            "scene_mjcf_sha256": hashlib.sha256(built["mjcf"].encode()).hexdigest(),
            "template_id": built["template_id"], "physics_owner": "python_mujoco",
            "capabilities": ["scripted_walk", "predefined_aim", "spray_exposure_proxy"] if mode == "mobile"
                            else ["fixed_base", "predefined_aim", "spray_exposure_proxy"],
            "units": {"length": "metres", "angle": "radians", "up_axis": "Z"}}


def _commit(run):
    run.setdefault("telemetry", {})["weave"] = config.TELEMETRY["weave"]
    run["telemetry"]["events"] = observability.status()
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
    _event(run, stage + ".failed", outcome=state, retryable=retryable, error=message)


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


def _new_run(sources):
    if not 1 <= len(sources) <= 3:
        raise PipelineError(422, "Select between one and three videos")
    run_id = f"r_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{secrets.token_hex(2)}"
    d = records.run_dir(run_id)
    d.mkdir(parents=True, exist_ok=True)
    refs = []
    try:
        for i, (src, filename, kind, label) in enumerate(sources, 1):
            view_id = f"V{i}"
            name = "clip.mp4" if i == 1 else f"clip_{view_id}.mp4"
            dst = d / name
            shutil.copyfile(src, dst)
            info = ingest.validate_clip(dst)
            refs.append({"view_id": view_id, "kind": kind, "filename": filename, "sha256": info["sha256"],
                         "duration_s": info["duration_s"], "local_path": f"runs/{run_id}/{name}", "s3_uri": None,
                         "label": label or CLIP_LABEL})
    except (ingest.IngestError, OSError) as e:
        shutil.rmtree(d, ignore_errors=True)
        raise PipelineError(422, str(e), False) from e
    run = {"run_id": run_id, "created_at": _now(), "state": "uploaded", "error": None,
           "clip_ref": refs[0], "video_refs": refs, "model_id": cosmos.MODEL_ID, "prompt_id": cosmos.PROMPT_ID,
           "analysis": None, "observations": None, "confirmed_target": None, "confirmed_targets": None,
           "scene": None, "instruction": None, "skill": None, "metrics": None, "simulation_video": None,
           "timings_s": {}, "telemetry": {"weave": config.TELEMETRY["weave"], "vast": "pending"}}
    _event(run, "ingest", provenance="manual", sources=refs, outcome="uploaded")
    records.save(run)
    records.archive(run, with_clip=True)
    _RUNS[run_id] = run
    return run


def create_from_upload(tmp_path: Path, filename):
    return create_from_uploads([(tmp_path, filename)])


def create_from_uploads(uploads):
    return _new_run([(p, name or "upload.mp4", "upload", CLIP_LABEL) for p, name in uploads])


def create_from_clip(clip_id):
    return create_from_clips([clip_id])


def create_from_clips(clip_ids):
    return create_from_sources([], clip_ids)


def create_from_sources(uploads, clip_ids):
    if not isinstance(clip_ids, list) or not all(isinstance(i, str) and i for i in clip_ids) or not 1 <= len(clip_ids) + len(uploads) <= 3:
        raise PipelineError(422, "Select between one and three videos")
    if len(set(clip_ids)) != len(clip_ids):
        raise PipelineError(422, "Duplicate clip IDs are not allowed")
    clips = {c["clip_id"]: c for c in list_clips()} if clip_ids else {}
    sources = []
    for clip_id in clip_ids:
        if clip_id not in clips:
            raise PipelineError(404, f"unknown clip_id {clip_id!r}")
        c = clips[clip_id]
        sources.append((config.CLIPS_DIR / c["filename"], c["filename"], "preloaded", c["label"]))
    sources.extend((p, name or "upload.mp4", "upload", CLIP_LABEL) for p, name in uploads)
    return _new_run(sources)


def source_video(run_id, view_id="V1"):
    run = get_run(run_id)
    refs = run.get("video_refs") or [dict(run["clip_ref"], view_id="V1")]
    ref = next((r for r in refs if r["view_id"] == view_id), None)
    if ref is None:
        raise PipelineError(404, "unknown video view")
    p = records.run_dir(run_id) / ("clip.mp4" if view_id == "V1" else f"clip_{view_id}.mp4")
    if not p.exists():
        raise PipelineError(404, "source video missing")
    return p


# ---------- stages ----------

def analyse(run_id):
    run = get_run(run_id)
    with _lock(run_id):
        err = run.get("error") or {}
        ok = run["state"] in ("uploaded", "analysed", "needs_review") or (run["state"] == "failed" and err.get("stage") == "analyse")
        if not ok:
            raise PipelineError(409, f"Cannot analyse in state {run['state']!r}")
        for k in DOWNSTREAM_OF_ANALYSE:
            run[k] = None
        for name in ("trajectory.json", "simulation.mp4", "scene.xml"):
            (records.run_dir(run_id) / name).unlink(missing_ok=True)
        run["error"], run["timings_s"], run["analysis"] = None, {}, None
        run["model_id"], run["prompt_id"] = cosmos.MODEL_ID, cosmos.PROMPT_ID
        refs = run.get("video_refs") or [dict(run["clip_ref"], view_id="V1")]
        multi = len(refs) > 1
        spatial_enabled = config.spatial_review_enabled()
        views, frames_for_fusion, fusion_frame_times, aggregate, failures = [], [], [], [], []
        t0 = time.time()
        _event(run, "analyse.started", source_count=len(refs), spatial_review_enabled=spatial_enabled)
        for ref in refs:
            vid = ref["view_id"]
            clip = source_video(run_id, vid)
            entry = {"view_id": vid, "state": "failed", "analysis": None, "observations": None, "error": None}
            views.append(entry)
            try:
                frames = ingest.extract_frames(clip, ref["duration_s"], records.run_dir(run_id) / ("frames" if not multi else f"frames_{vid}"))
                _event(run, "frame_selection", view_id=vid, source_sha256=ref["sha256"],
                       frames=[{"frame_id": f"{vid}:{f['t_s']}", "t_s": f["t_s"],
                                **observability.artifact(f["path"])} for f in frames])
                frames_for_fusion.append(frames[len(frames) // 2]["path"])
                fusion_frame_times.append(frames[len(frames) // 2]["t_s"])
                with ThreadPoolExecutor(1) as ex:
                    yfut = ex.submit(yolo.detect, clip)
                    _event(run, "cosmos.started", view_id=vid, source_sha256=ref["sha256"],
                           provider="cosmos", model_id=cosmos.MODEL_ID, prompt_id=cosmos.PROMPT_ID,
                           cache_enabled=config.use_cache())
                    if multi or spatial_enabled:
                        analysis, obs = cosmos.analyse(frames, ref["duration_s"], ref["sha256"], allow_empty=True)
                    else:
                        analysis, obs = cosmos.analyse(frames, ref["duration_s"], ref["sha256"])
                    _event(run, "cosmos.validation", provenance="cached/replayed" if analysis.get("cached") else "live",
                           view_id=vid, source_sha256=ref["sha256"], provider="cosmos", model_id=cosmos.MODEL_ID,
                           prompt_id=cosmos.PROMPT_ID, latency_s=analysis.get("latency_s"),
                           original_evidence=records.evidence(run_id, f"cosmos_{vid}", obs),
                           raw_result=records.evidence(run_id, f"cosmos_raw_{vid}", analysis), outcome="valid")
                    entry["analysis"] = analysis
                    if spatial_enabled:
                        try:
                            _event(run, "grounding.started", view_id=vid, provider="openai",
                                   model_id=config.ASTRA_MODEL, prompt_id=grounding.PROMPT_ID)
                            review, obs = grounding.review(frames, ref["duration_s"], obs)
                            analysis["spatial_review"] = review
                            _event(run, "grounding", provenance="live", view_id=vid, provider="openai",
                                   model_id=review.get("model_id"), prompt_id=grounding.PROMPT_ID,
                                   reviewed_evidence=records.evidence(run_id, f"reviewed_{vid}", obs),
                                   review=records.evidence(run_id, f"grounding_{vid}", review))
                        except (grounding.GroundingUnavailable, grounding.InvalidGrounding) as e:
                            analysis["spatial_review"] = e.review_metadata
                            raise
                    else:
                        analysis["spatial_review"] = {"status": "disabled", "model_id": None,
                                                      "reason": "API spatial review is not configured; boxes are unreviewed."}
                    objects, ynote = yfut.result()
                analysis["yolo"] = ynote
                obs["objects"] = objects
                entry.update(state="analysed", analysis=analysis, observations=obs)
                for f in obs["fire_sources"]:
                    aggregate.append({**f, "id": f"{vid}:{f['id']}" if multi else f["id"], "view_id": vid, "source_id": f["id"]})
            except (ingest.IngestError, cosmos.UpstreamError, cosmos.InvalidOutput,
                    grounding.GroundingUnavailable, grounding.InvalidGrounding) as e:
                entry["analysis"] = getattr(e, "analysis", None) or entry["analysis"]
                entry["error"] = str(e)
                entry["state"] = "needs_review" if isinstance(e, (cosmos.InvalidOutput, grounding.InvalidGrounding)) else "failed"
                failures.append(entry)
                _event(run, "analyse.view_failed", view_id=vid, error_type=type(e).__name__, error=str(e))
        run["timings_s"]["analyse"] = round(time.time() - t0, 2)
        if not multi:
            run["analysis"] = dict(views[0]["analysis"]) if views[0]["analysis"] else None
            if failures:
                _fail(run, "analyse", failures[0]["error"], True, state=failures[0]["state"])
                return _commit(run)
            run["analysis"]["views"] = views
        else:
            run["analysis"] = {"views": views, "raw_text": "\n\n".join(f"{v['view_id']}:\n{(v['analysis'] or {}).get('raw_text', '')}" for v in views),
                               "latency_s": run["timings_s"]["analyse"], "association_candidates": []}
            if failures:
                state = "failed" if any(v["state"] == "failed" for v in failures) else "needs_review"
                _fail(run, "analyse", "; ".join(f"{v['view_id']}: {v['error']}" for v in failures), True, state=state)
                return _commit(run)
        if not aggregate:
            _fail(run, "analyse", "Cosmos reported no fire sources in any view", True, state="needs_review")
            return _commit(run)
        first = views[0]["observations"]
        obs = {**first, "fire_sources": aggregate}
        if multi:
            # Preserve each camera's uncertainty and never promote one view's inference
            # into an incident-wide cause, scale or depth measurement.
            obs["view_unknowns"] = [{"view_id": v["view_id"], "unknowns": list(v["observations"].get("unknowns") or [])} for v in views]
            obs["unknowns"] = list(dict.fromkeys(u for entry in obs["view_unknowns"] for u in entry["unknowns"]))
            obs["cause"], obs["scale"], obs["depth_m"] = None, None, None
            for name in ("cause", "scale", "depth"):
                if name not in obs["unknowns"] and not (name == "depth" and "depth_m" in obs["unknowns"]):
                    obs["unknowns"].append(name)
            obs["scene_description"] = " ".join(f"{v['view_id']}: {v['observations'].get('scene_description') or ''}" for v in views)
            fusion_views = [{**v, "observations": {**v["observations"], "fire_sources": [f for f in aggregate if f["view_id"] == v["view_id"]]}} for v in views]
            # Original Cosmos suggestions remain audit evidence. They cannot establish
            # identity by themselves or initialize physical groups in the workbench.
            run["analysis"]["cosmos_association"] = cosmos.propose_associations(fusion_views, frames_for_fusion)
            _event(run, "cosmos.association", provenance="live" if not run["analysis"]["cosmos_association"].get("error") else "deterministic",
                   provider="cosmos", model_id=cosmos.MODEL_ID,
                   result=records.evidence(run_id, "cosmos_association", run["analysis"]["cosmos_association"]))
            association = matching.propose([{**v, "frame_t_s": t} for v, t in zip(fusion_views, fusion_frame_times)], frames_for_fusion)
            _event(run, "association", provenance="live" if association.get("model_id") else "deterministic",
                   provider="openai", model_id=association.get("model_id"), prompt_id=matching.PROMPT_ID,
                   frame_times_s=fusion_frame_times,
                   evidence=records.evidence(run_id, "association", association), outcome=association.get("status"))
            run["analysis"]["association"] = association
            run["analysis"]["association_candidates"] = association["candidates"]
            obs["association_candidates"] = association["candidates"]
            obs["association_status"] = {k: association.get(k) for k in ("room_status", "status", "uncertainties", "evidence")}
            if association.get("error"):
                run["analysis"]["association_error"] = association["error"]

        else:
            obs["association_candidates"] = []
        warnings = []
        for v in views:
            sightings = [f for f in aggregate if f["view_id"] == v["view_id"]]
            boxes = {}
            for f in sightings:
                boxes.setdefault(tuple(f["bbox_normalized"]), []).append(f["id"])
            for ids in boxes.values():
                if len(ids) > 1:
                    warnings.append({"view_id": v["view_id"], "members": ids,
                                     "message": "Multiple detections have identical bounding boxes; review whether they are duplicates."})
        obs["evidence_warnings"] = warnings
        run["observations"], run["state"] = obs, "analysed"
        _event(run, "analyse.completed", evidence=records.evidence(run_id, "observations", obs),
               source_count=len(refs), fire_sighting_count=len(aggregate), wall_latency_s=run["timings_s"]["analyse"])
        _commit(run)
        records.archive(run)
        return run


def confirm(run_id, fire_id, zone):
    from . import scene
    run = get_run(run_id)
    with _lock(run_id):
        if len(run.get("video_refs") or [run["clip_ref"]]) > 1:
            raise PipelineError(422, "Multi-view incidents require targets and excluded for grouped confirmation")
        if run["state"] not in ("analysed", "confirmed", "scene_ready", "blocked", "completed"):
            raise PipelineError(409, f"Cannot confirm in state {run['state']!r}")
        fs = {f["id"]: f for f in run["observations"]["fire_sources"]}
        if fire_id not in fs:
            raise PipelineError(422, f"Unknown fire_id {fire_id!r}; valid: {sorted(fs)}")
        if zone not in scene.ZONES:
            raise PipelineError(422, f"Unknown zone {zone!r}; valid: {sorted(scene.ZONES)}")
        for k in ("scene", "instruction", "skill", "metrics", "simulation_video", "simulation_identity"):
            run[k] = None
        for name in ("scene.xml", "trajectory.json", "simulation.mp4"):
            (records.run_dir(run_id) / name).unlink(missing_ok=True)
        run["timings_s"] = {k: v for k, v in run["timings_s"].items() if k == "analyse"}
        run["error"] = None
        run["response_mode"], run["confirmed_targets"], run["excluded"] = "legacy", None, []
        run["confirmed_target"] = {
            "fire_id": fire_id, "zone": zone, "image_bbox_normalized": fs[fire_id]["bbox_normalized"],
            "template_position_m": list(scene.ZONES[zone]["anchor"]),
            "position_provenance": "template-assumed (wh_aisle_v1 zone anchor)"}
        run["state"] = "confirmed"
        _event(run, "confirmation", provenance="manual", target=run["confirmed_target"], exclusions=[])
        return _commit(run)


def confirm_targets(run_id, targets, excluded):
    from . import mobile
    run = get_run(run_id)
    with _lock(run_id):
        if run["state"] not in ("analysed", "confirmed", "scene_ready", "blocked", "completed"):
            raise PipelineError(409, f"Cannot confirm in state {run['state']!r}")
        if not isinstance(targets, list) or not 1 <= len(targets) <= 12 or not isinstance(excluded, list):
            raise PipelineError(422, "targets must contain one to twelve groups and excluded must be a list")
        fires = {f["id"]: f for f in run["observations"]["fire_sources"]}
        seen, used_slots, confirmed = set(), set(), []
        for target in targets:
            if not isinstance(target, dict) or not isinstance(target.get("members"), list) or not target["members"]:
                raise PipelineError(422, "Each target requires members")
            members = target["members"]
            if not all(isinstance(m, str) and m in fires for m in members) or len(set(members)) != len(members) or seen.intersection(members):
                raise PipelineError(422, "Unknown or repeated evidence in targets")
            if len({fires[m].get("view_id", "V1") for m in members}) != len(members):
                raise PipelineError(422, "A target may contain at most one sighting per view")
            zone, slot = target.get("zone"), target.get("slot")
            if not isinstance(zone, str) or not isinstance(slot, int) or isinstance(slot, bool):
                raise PipelineError(422, "Each target requires a zone and integer slot")
            if (zone, slot) in used_slots:
                raise PipelineError(422, "Each target needs a distinct zone and slot")
            try:
                pos = mobile.target_position(zone, slot)
            except (ValueError, KeyError, IndexError) as e:
                raise PipelineError(422, f"Invalid zone or slot: {e}") from e
            seen.update(members)
            used_slots.add((zone, slot))
            supported = any(set(members).issubset(set(c["members"]))
                            for c in run["analysis"].get("association_candidates", []))
            association_provenance = ("operator-confirmed single-view sighting; no cross-camera match claimed"
                                      if len(members) == 1 else
                                      "operator-confirmed visually and projectively supported proposal"
                                      if supported else
                                      "operator-authored grouping; cross-camera identity is unverified")
            confirmed.append({"fire_id": f"T{len(confirmed)+1}", "members": members, "zone": zone, "slot": slot,
                              "template_position_m": list(pos), "position_provenance": "template-assumed (wh_mobile_v1 zone slot)",
                              "association_provenance": association_provenance,
                              "image_evidence": [fires[m] for m in members], "image_bbox_normalized": fires[members[0]]["bbox_normalized"]})
        for exclusion in excluded:
            if not isinstance(exclusion, dict) or not isinstance(exclusion.get("id"), str) or exclusion["id"] not in fires or exclusion["id"] in seen or not isinstance(exclusion.get("reason"), str) or not exclusion["reason"].strip():
                raise PipelineError(422, "Each exclusion needs a unique known evidence ID and a reason")
            seen.add(exclusion["id"])
        if seen != set(fires):
            raise PipelineError(422, "Every sighting must appear exactly once in a target or exclusion")
        for k in ("scene", "instruction", "skill", "metrics", "simulation_video", "simulation_identity"):
            run[k] = None
        for name in ("scene.xml", "trajectory.json", "simulation.mp4"):
            (records.run_dir(run_id) / name).unlink(missing_ok=True)
        run["confirmed_targets"], run["confirmed_target"], run["response_mode"] = confirmed, confirmed[0], "mobile"
        run["excluded"] = excluded
        run["timings_s"] = {k: v for k, v in run["timings_s"].items() if k == "analyse"}
        run["error"], run["state"] = None, "confirmed"
        _event(run, "confirmation", provenance="manual", targets=confirmed, exclusions=excluded,
               evidence=records.evidence(run_id, "confirmed", {"targets": confirmed, "excluded": excluded}))
        return _commit(run)


def _scene_obj(run):
    """Sim-facing scene dict: deterministic rebuild from observations + confirmed target (includes mjcf, fires...)."""
    if run.get("response_mode") == "mobile":
        from . import mobile
        return mobile.build_scene(run["confirmed_targets"], run["scene"]["settings"])
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
        if run.get("response_mode") == "mobile":
            from . import mobile
            run["error"], run["instruction"], run["skill"], run["scene"] = None, None, None, None
            t0 = time.time()
            try:
                evidence = {**run["observations"], "excluded": run.get("excluded", []), "run_id": run_id}
                with observability.context(run_id=run_id):
                    ins, skill, settings = planner.make_mobile_plan(run["confirmed_targets"], evidence)
                built = mobile.build_scene(run["confirmed_targets"], settings)
                run["simulation_identity"] = _identity(built, "mobile")
            except planner.PlannerUnavailable as e:
                _fail(run, "plan", str(e), True)
                return _commit(run)
            except (planner.PlanInvalid, ValueError) as e:
                _fail(run, "plan", str(e), True, state="blocked")
                return _commit(run)
            d = records.run_dir(run_id)
            (d / "scene.xml").write_text(built["mjcf"])
            run["scene"] = {k: v for k, v in built.items() if k != "mjcf"}
            run["scene"]["mjcf_path"] = f"runs/{run_id}/scene.xml"
            run["instruction"], run["skill"] = ins, skill
            _event(run, "planner.selected", provenance="live", provider=ins.get("provider", "astra"),
                   model_id=ins.get("model_id"), prompt_id=ins.get("prompt_id"),
                   result=records.evidence(run_id, "planner", {"instruction": ins, "skill": skill, "settings": settings}))
            _event(run, "scene.constructed", scene_artifact=observability.artifact(d / "scene.xml"),
                   placements=built.get("placements"), settings=settings)
            run["timings_s"]["scene"] = round(time.time() - t0, 2)
            run["timings_s"]["plan"] = ins.get("latency_s", 0)
            run["state"] = "scene_ready"
            _commit(run)
            records.archive(run, extra_files=("scene.xml",))
            return run
        ct = run["confirmed_target"]
        fid, zone = ct["fire_id"], ct["zone"]
        run["error"], run["instruction"], run["skill"] = None, None, None
        t0 = time.time()
        try:
            built = scene_mod.build_scene(run["observations"]["fire_sources"], {fid: zone}, fid)
        except ValueError as e:
            _fail(run, "scene", str(e), False, state="blocked")
            return _commit(run)
        run["simulation_identity"] = _identity(built, "legacy")
        d = records.run_dir(run_id)
        (d / "scene.xml").write_text(built["mjcf"])
        _event(run, "scene.constructed", scene_artifact=observability.artifact(d / "scene.xml"), placements=built.get("placements"))
        run["scene"] = {"template_id": built["template_id"], "source_zone_mapping": built["source_zone_mapping"],
                        "placements": built["placements"], "target_pos": built["target_pos"],
                        "mjcf_path": f"runs/{run_id}/scene.xml", "settings": built["settings"]}
        run["timings_s"]["scene"] = round(time.time() - t0, 2)
        ok_reach, why = scene_mod.check_reachable(built, fid)
        if not ok_reach:
            _fail(run, "scene", f"Execution blocked: target {fid} in zone '{zone}' is not reachable ({why})",
                  False, state="blocked")
            return _commit(run)
        fire = next(f for f in run["observations"]["fire_sources"] if f["id"] == fid)
        evidence = {key: fire[key] for key in ("description", "location_description", "burning_object",
                                              "smoke_description", "nearby_objects", "bbox_normalized")
                    if fire.get(key)}
        if run["observations"].get("scene_description"):
            evidence["scene_description"] = run["observations"]["scene_description"]
        desc = json.dumps(evidence)
        with observability.context(run_id=run_id):
            ins, skill = planner.make_plan(fid, zone, desc)
        _event(run, "planner.selected", provenance="deterministic fallback" if ins.get("source") == "fallback" else "live",
               provider="deterministic" if ins.get("source") == "fallback" else "wandb", model_id=ins.get("model_id"), prompt_id=ins.get("prompt_id"),
               result=records.evidence(run_id, "planner_legacy", {"instruction": ins, "skill": skill}))
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
        ok = run["state"] == "scene_ready" or (run["state"] == "failed" and err.get("stage") in ("run", "export") and run.get("skill"))
        if not ok:
            raise PipelineError(409, f"Cannot run in state {run['state']!r}")
        run["error"], run["metrics"], run["simulation_video"] = None, None, None
        for name in ("trajectory.json", "simulation.mp4"):
            (records.run_dir(run_id) / name).unlink(missing_ok=True)
        t0 = time.time()
        _event(run, "simulation.started", skill=run["skill"], scene_revision=observability.digest(run.get("scene")))
        try:
            if run.get("response_mode") == "mobile":
                from . import mobile
                metrics, traj = mobile.simulate(_scene_obj(run), run["skill"])
            else:
                metrics, traj = sim.simulate(_scene_obj(run), run["skill"])
        except ValueError as e:
            _fail(run, "run", str(e), False)
            return _commit(run)
        except Exception as e:  # noqa: BLE001
            _fail(run, "run", f"Simulation error: {type(e).__name__}: {e}", True)
            return _commit(run)
        (records.run_dir(run_id) / "trajectory.json").write_text(json.dumps(traj))
        run["metrics"] = metrics
        _event(run, "simulation.outcome", metrics=metrics, wall_duration_s=round(time.time() - t0, 4),
               trajectory=observability.artifact(records.run_dir(run_id) / "trajectory.json"))
        if run.get("response_mode") == "mobile":
            from . import rendering
            try:
                run["simulation_video"] = rendering.export_video(_scene_obj(run), traj, records.run_dir(run_id) / "simulation.mp4")
                _event(run, "recording.export", outcome="ok", recording=observability.artifact(records.run_dir(run_id) / "simulation.mp4"))
            except Exception as e:  # noqa: BLE001
                (records.run_dir(run_id) / "simulation.mp4").unlink(missing_ok=True)
                run["simulation_video"] = None
                _fail(run, "export", f"Simulation video export failed: {type(e).__name__}: {e}", True)
                return _commit(run)
        run["timings_s"]["run"] = round(time.time() - t0, 2)
        run["state"] = "completed"
        _commit(run)
        records.archive(run, extra_files=("trajectory.json", "simulation.mp4"))
        return run


def reset(run_id):
    run = get_run(run_id)
    with _lock(run_id):
        err = run.get("error") or {}
        ok = run["state"] in ("completed", "scene_ready") or (
            run["state"] == "failed" and err.get("stage") in ("run", "export") and run.get("skill"))
        if not ok:
            raise PipelineError(409, f"Cannot reset in state {run['state']!r}")
        (records.run_dir(run_id) / "trajectory.json").unlink(missing_ok=True)
        (records.run_dir(run_id) / "simulation.mp4").unlink(missing_ok=True)
        run["simulation_video"] = None
        run["metrics"], run["error"], run["state"] = None, None, "scene_ready"
        run["timings_s"].pop("run", None)
        return _commit(run)


def trajectory(run_id):
    get_run(run_id)
    p = records.run_dir(run_id) / "trajectory.json"
    if not p.exists():
        raise PipelineError(404, "no trajectory yet")
    return p


def simulation_video(run_id):
    run = get_run(run_id)
    p = records.run_dir(run_id) / "simulation.mp4"
    if run.get("state") != "completed" or not run.get("simulation_video") or not p.exists():
        raise PipelineError(404, "no simulation recording yet")
    return p
