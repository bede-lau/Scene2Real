"""Persist the latest long-running operation for each run.

The lock file is held for the whole operation, including across processes. If
the process dies, the OS releases the lock and the next poll marks the job
interrupted instead of reporting progress forever.
"""
import fcntl
import json
import os
import secrets
import threading
from datetime import datetime, timezone

from . import pipeline, records

_STEPS = {"analyse": "analyse", "scene": "build_scene", "run": "run_sim"}
_ACTIVE = {"pending", "running"}


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _path(run_id):
    return records.run_dir(run_id) / "operation.json"


def _read(run_id):
    path = _path(run_id)
    return json.loads(path.read_text()) if path.exists() else None


def _write(run_id, job):
    path = _path(run_id)
    tmp = path.with_name(f".{path.name}.{secrets.token_hex(8)}.tmp")
    try:
        tmp.write_text(json.dumps(job))
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def _try_lock(run_id):
    lock = (records.run_dir(run_id) / ".operation.lock").open("a")
    try:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        lock.close()
        return None
    return lock


def _release(lock):
    fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
    lock.close()


def _interrupt(job):
    job.update(status="failed", finished_at=_now(), error={
        "detail": "The server restarted before this operation finished. Please try again.",
        "retryable": True, "status": 503,
    })
    return job


def latest(run_id, operation_id=None):
    pipeline.get_run(run_id)  # validate existence and path before opening any files
    job = _read(run_id)
    if not job or (operation_id is not None and job["id"] != operation_id):
        raise pipeline.PipelineError(404, "operation not found")
    if job["status"] in _ACTIVE:
        lock = _try_lock(run_id)
        if lock is not None:
            try:
                # The operation may have finished between the read and lock.
                job = _read(run_id)
                if job and job["status"] in _ACTIVE:
                    _write(run_id, _interrupt(job))
            finally:
                _release(lock)
    if not job or (operation_id is not None and job["id"] != operation_id):
        raise pipeline.PipelineError(404, "operation not found")
    return job


def _execute(run_id, job, lock):
    try:
        job.update(status="running", started_at=_now())
        _write(run_id, job)
        result = getattr(pipeline, _STEPS[job["operation"]])(run_id)
        job.update(status="completed", finished_at=_now(), result=result)
    except pipeline.PipelineError as exc:
        job.update(status="failed", finished_at=_now(), error={
            "detail": exc.detail, "retryable": exc.retryable, "status": exc.status,
        })
    except Exception:  # Do not expose arbitrary upstream exceptions or credentials.
        job.update(status="failed", finished_at=_now(), error={
            "detail": "The operation failed unexpectedly. Please try again.",
            "retryable": True, "status": 500,
        })
    finally:
        try:
            _write(run_id, job)
        finally:
            _release(lock)


def start(run_id, operation):
    if operation not in _STEPS:
        raise pipeline.PipelineError(422, "operation must be analyse, scene, or run")
    pipeline.get_run(run_id)
    lock = _try_lock(run_id)
    if lock is None:
        job = _read(run_id)
        if job and job["status"] in _ACTIVE and job["operation"] == operation:
            return job
        raise pipeline.PipelineError(409, "Another operation is already running for this run", True)
    try:
        job = {"id": secrets.token_hex(16), "run_id": run_id, "operation": operation,
               "status": "pending", "created_at": _now()}
        _write(run_id, job)
        thread = threading.Thread(target=_execute, args=(run_id, job.copy(), lock), daemon=True)
        thread.start()
    except Exception:
        _release(lock)
        raise
    return job
