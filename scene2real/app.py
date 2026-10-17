"""FastAPI app: contract routes + static frontend."""
import json
import shutil
import tempfile
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import config, pipeline, records

app = FastAPI(title="Scene2Real")


@app.on_event("startup")
def _startup():
    config.RUNS_DIR.mkdir(parents=True, exist_ok=True)
    config.init_weave()


@app.exception_handler(pipeline.PipelineError)
async def _pe(_, e: pipeline.PipelineError):
    return JSONResponse({"detail": e.detail, "retryable": e.retryable}, status_code=e.status)


@app.exception_handler(Exception)
async def _unhandled(_, e: Exception):
    return JSONResponse({"detail": f"{type(e).__name__}: {e}", "retryable": True}, status_code=500)


@app.get("/api/clips")
def clips():
    return pipeline.list_clips()


@app.get("/api/zones")
def zones():
    from . import mobile, scene
    out = {}
    for z, v in scene.ZONES.items():
        try:
            probe = scene.build_scene([{"id": "Z", "bbox_normalized": [0.4, 0.4, 0.6, 0.6], "timestamps_s": [0.0],
                                        "description": ""}], {"Z": z}, "Z")
            reachable = bool(scene.check_reachable(probe, "Z")[0])
        except Exception:  # noqa: BLE001
            reachable = z != "behind_robot"
        out[z] = {"anchor": v["anchor"], "label": v.get("label", z), "reachable": reachable, "slots": mobile.SLOTS.get(z, [])}
    return out


@app.post("/api/runs")
async def create_run(request: Request):
    ctype = request.headers.get("content-type", "")
    if ctype.startswith("multipart/"):
        form = await request.form()
        legacy = form.getlist("file")
        uploads = form.getlist("files")
        raw_ids = form.get("clip_ids")
        if legacy and (uploads or raw_ids is not None) or len(legacy) > 1:
            raise pipeline.PipelineError(422, "Use either file or the files/clip_ids form")
        uploads = legacy or uploads
        try:
            ids = json.loads(raw_ids) if raw_ids is not None else []
        except (ValueError, TypeError):
            raise pipeline.PipelineError(422, "clip_ids must be a JSON array")
        if not isinstance(ids, list) or not 1 <= len(uploads) + len(ids) <= 3 or any(not hasattr(up, "read") for up in uploads):
            raise pipeline.PipelineError(422, "Select between one and three videos")
        tmpdir = Path(tempfile.mkdtemp(prefix="s2r_"))
        sources = []
        try:
            for i, up in enumerate(uploads):
                tmp = tmpdir / f"upload_{i}.mp4"
                size = 0
                with open(tmp, "wb") as f:
                    while chunk := await up.read(1 << 20):
                        size += len(chunk)
                        if size > config.MAX_UPLOAD_BYTES:
                            raise pipeline.PipelineError(413, "File exceeds 200 MB limit")
                        f.write(chunk)
                sources.append((tmp, up.filename))
            return pipeline.create_from_sources(sources, ids)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)
    try:
        body = await request.json()
    except Exception:  # noqa: BLE001
        raise pipeline.PipelineError(422, "expected multipart files or JSON clip_ids")
    if not isinstance(body, dict) or ("clip_id" in body and "clip_ids" in body):
        raise pipeline.PipelineError(422, "Provide clip_id or clip_ids")
    ids = body.get("clip_ids") if "clip_ids" in body else [body.get("clip_id")]
    return pipeline.create_from_clips(ids)


@app.get("/api/runs/{run_id}")
def get_run(run_id: str):
    return pipeline.get_run(run_id)


@app.get("/api/runs/{run_id}/video")
def video(run_id: str):
    return FileResponse(pipeline.source_video(run_id), media_type="video/mp4")


@app.get("/api/runs/{run_id}/video/{view_id}")
def view_video(run_id: str, view_id: str):
    return FileResponse(pipeline.source_video(run_id, view_id), media_type="video/mp4")


@app.get("/api/runs/{run_id}/simulation-video")
def simulation_video(run_id: str):
    return FileResponse(pipeline.simulation_video(run_id), media_type="video/mp4")


@app.post("/api/runs/{run_id}/analyse")
def analyse(run_id: str):
    return pipeline.analyse(run_id)


@app.post("/api/runs/{run_id}/confirm")
async def confirm(run_id: str, request: Request):
    try:
        body = await request.json()
    except Exception:  # noqa: BLE001
        body = None
    if isinstance(body, dict) and "targets" in body:
        if "fire_id" in body or "zone" in body:
            raise pipeline.PipelineError(422, "Use a single confirmation format")
        return pipeline.confirm_targets(run_id, body["targets"], body.get("excluded", []))
    if not isinstance(body, dict) or not body.get("fire_id") or not body.get("zone"):
        raise pipeline.PipelineError(422, "body {fire_id, zone} required")
    return pipeline.confirm(run_id, body["fire_id"], body["zone"])


@app.post("/api/runs/{run_id}/scene")
def scene_step(run_id: str):
    return pipeline.build_scene(run_id)


@app.post("/api/runs/{run_id}/run")
def run_step(run_id: str):
    return pipeline.run_sim(run_id)


@app.post("/api/runs/{run_id}/reset")
def reset(run_id: str):
    return pipeline.reset(run_id)


@app.get("/api/runs/{run_id}/trajectory")
def traj(run_id: str):
    return FileResponse(pipeline.trajectory(run_id), media_type="application/json")


from .live import router as live_router

app.include_router(live_router)

config.STATIC_DIR.mkdir(exist_ok=True)
app.mount("/", StaticFiles(directory=str(config.STATIC_DIR), html=True), name="static")
