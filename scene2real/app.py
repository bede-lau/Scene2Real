"""FastAPI app: contract routes + static frontend."""
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
    from . import scene
    out = {}
    for z, v in scene.ZONES.items():
        try:
            probe = scene.build_scene([{"id": "Z", "bbox_normalized": [0.4, 0.4, 0.6, 0.6], "timestamps_s": [0.0],
                                        "description": ""}], {"Z": z}, "Z")
            reachable = bool(scene.check_reachable(probe, "Z")[0])
        except Exception:  # noqa: BLE001
            reachable = z != "behind_robot"
        out[z] = {"anchor": v["anchor"], "label": v.get("label", z), "reachable": reachable}
    return out


@app.post("/api/runs")
async def create_run(request: Request):
    ctype = request.headers.get("content-type", "")
    if ctype.startswith("multipart/"):
        form = await request.form()
        up = form.get("file")
        if up is None or not hasattr(up, "read"):
            raise pipeline.PipelineError(422, "multipart field 'file' required")
        tmpdir = Path(tempfile.mkdtemp(prefix="s2r_"))
        tmp = tmpdir / "upload.mp4"
        size = 0
        with open(tmp, "wb") as f:
            while chunk := await up.read(1 << 20):
                size += len(chunk)
                if size > config.MAX_UPLOAD_BYTES:
                    shutil.rmtree(tmpdir, ignore_errors=True)
                    raise pipeline.PipelineError(413, "File exceeds 200 MB limit")
                f.write(chunk)
        try:
            return pipeline.create_from_upload(tmp, up.filename)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)
    try:
        body = await request.json()
    except Exception:  # noqa: BLE001
        raise pipeline.PipelineError(422, "expected multipart file or JSON {clip_id}")
    if not isinstance(body, dict) or not body.get("clip_id"):
        raise pipeline.PipelineError(422, "clip_id required")
    return pipeline.create_from_clip(str(body["clip_id"]))


@app.get("/api/runs/{run_id}")
def get_run(run_id: str):
    return pipeline.get_run(run_id)


@app.get("/api/runs/{run_id}/video")
def video(run_id: str):
    pipeline.get_run(run_id)
    return FileResponse(records.run_dir(run_id) / "clip.mp4", media_type="video/mp4")


@app.post("/api/runs/{run_id}/analyse")
def analyse(run_id: str):
    return pipeline.analyse(run_id)


@app.post("/api/runs/{run_id}/confirm")
async def confirm(run_id: str, request: Request):
    try:
        body = await request.json()
    except Exception:  # noqa: BLE001
        body = None
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


config.STATIC_DIR.mkdir(exist_ok=True)
app.mount("/", StaticFiles(directory=str(config.STATIC_DIR), html=True), name="static")
