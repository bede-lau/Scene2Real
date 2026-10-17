"""Bounded, nonblocking milestone telemetry with explicit cross-request correlation.

Physics workers only enqueue: disk and optional Weave calls run on a daemon worker.
Events are linked by trace_group_id; they do not pretend separate HTTP calls share
an implicit Weave parent. Local evidence remains available without W&B credentials.
"""
from __future__ import annotations

import contextlib
import contextvars
import hashlib
import json
import math
import queue
import re
import subprocess
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from . import config

_CONTEXT = contextvars.ContextVar("scene2real_event_context", default={})
_QUEUE = queue.Queue(maxsize=256)
_REMOTE_QUEUE = queue.Queue(maxsize=64)
_REMOTE_WORKER = None
_START_LOCK = threading.Lock()
_WORKER = None
_STATE = {"enqueued": 0, "written": 0, "dropped": 0, "local_errors": 0,
          "weave_submitted": 0, "weave_errors": 0, "weave_dropped": 0, "last_error": None}
_SECRET_KEY = re.compile(r"authorization|api.?key|secret|password|access.?token|bearer|signed.?url|headers", re.I)
_SAFE_ID = re.compile(r"^[A-Za-z0-9_.-]{1,100}$")
_PROVENANCE = {"live", "cached/replayed", "mocked", "manual", "deterministic", "deterministic fallback"}


def sanitize(value, *, max_string=8000, max_items=200):
    """Strip sensitive keys and URL credentials before either persistence sink."""
    if isinstance(value, dict):
        return {str(k): "[redacted]" if _SECRET_KEY.search(str(k)) else sanitize(v, max_string=max_string, max_items=max_items)
                for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [sanitize(v, max_string=max_string, max_items=max_items) for v in value[:max_items]]
    if isinstance(value, str):
        for key in ("WANDB_API_KEY", "OPENAI_API_KEY", "ACCESS_KEY", "SECRET_KEY", "COREWEAVE_API_KEY", "GPU_BEARER_TOKEN"):
            secret = config.get(key)
            if secret and len(secret) >= 8:
                value = value.replace(secret, "[redacted]")
        value = re.sub(r"(?i)bearer\s+[^\s\"']+", "Bearer [redacted]", value)
        def clean_url(match):
            u = urlsplit(match.group(0))
            return urlunsplit((u.scheme, u.netloc.rsplit("@", 1)[-1], u.path, "", ""))
        return re.sub(r"https?://[^\s\"'<>]+", clean_url, value)[:max_string]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if value is None or isinstance(value, (int, float, bool)):
        return value
    return str(value)[:max_string]


def digest(value):
    return hashlib.sha256(json.dumps(sanitize(value, max_string=None, max_items=None), sort_keys=True, default=str).encode()).hexdigest()


def artifact(path):
    path = Path(path)
    try:
        h = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                h.update(chunk)
        return {"path": str(path), "sha256": h.hexdigest(), "bytes": path.stat().st_size}
    except OSError as exc:
        return {"path": str(path), "status": "skipped", "error_type": type(exc).__name__}


def _source_commit():
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=config.ROOT,
                                       stderr=subprocess.DEVNULL, timeout=1, text=True).strip()
    except Exception:
        return "unknown"


_SOURCE_COMMIT = _source_commit()


@contextlib.contextmanager
def context(**ids):
    merged = {**_CONTEXT.get(), **ids}
    token = _CONTEXT.set(merged)
    weave_context = None
    try:
        # Only attach metadata to already configured SDK calls. Never initialise
        # telemetry here or suppress exceptions raised by the provider body.
        if config.TELEMETRY.get("weave") == "ok":
            try:
                import weave
                weave_context = weave.attributes(sanitize(merged))
                weave_context.__enter__()
            except Exception:
                weave_context = None
        try:
            yield
        finally:
            if weave_context is not None:
                try:
                    weave_context.__exit__(None, None, None)
                except Exception:
                    pass
    finally:
        _CONTEXT.reset(token)


def _remote_event(event):
    """Small Weave op: inputs already sanitized and bounded."""
    return {"event_id": event["event_id"], "stage": event["stage"]}


# Lazy decoration avoids importing the SDK on physics-worker startup.
_REMOTE_OP = None


def _send_weave(event):
    global _REMOTE_OP
    import weave
    if _REMOTE_OP is None:
        _REMOTE_OP = config.weave_op(_remote_event)
    with weave.attributes({k: event.get(k) for k in
                           ("trace_group_id", "run_id", "session_id", "parent_run_id", "stage", "source_commit", "provenance")}):
        _REMOTE_OP(event)


def _consume(item):
    event, path = item
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a") as stream:
            stream.write(json.dumps(event, allow_nan=False) + "\n")
        _STATE["written"] += 1
    except Exception as exc:
        _STATE["local_errors"] += 1
        _STATE["last_error"] = f"local: {type(exc).__name__}"
    if config.TELEMETRY.get("weave") == "ok":
        try:
            _REMOTE_QUEUE.put_nowait(event)
        except queue.Full:
            _STATE["weave_dropped"] += 1


def _remote_work():
    while True:
        event = _REMOTE_QUEUE.get()
        try:
            _send_weave(event)
            _STATE["weave_submitted"] += 1  # SDK submission, not remote persistence
        except Exception as exc:
            _STATE["weave_errors"] += 1
            _STATE["last_error"] = f"weave: {type(exc).__name__}"
        finally:
            _REMOTE_QUEUE.task_done()


def _work():
    while True:
        item = _QUEUE.get()
        try:
            _consume(item)
        except Exception as exc:
            _STATE["last_error"] = type(exc).__name__
        finally:
            _QUEUE.task_done()


def _ensure_worker():
    global _WORKER, _REMOTE_WORKER
    with _START_LOCK:
        if _WORKER is None or not _WORKER.is_alive():
            _WORKER = threading.Thread(target=_work, name="scene2real-telemetry", daemon=True)
            _WORKER.start()
        if _REMOTE_WORKER is None or not _REMOTE_WORKER.is_alive():
            _REMOTE_WORKER = threading.Thread(target=_remote_work, name="scene2real-weave", daemon=True)
            _REMOTE_WORKER.start()


def emit(stage, *, run_id=None, session_id=None, parent_run_id=None, provenance="live", **attrs):
    """Enqueue a milestone, never raise or authorize motion. Returns event ID or None.

    Explicit IDs are required across background thread boundaries. Queue saturation
    drops telemetry (visible in status), never blocks simulation. No retries.
    """
    try:
        inherited = _CONTEXT.get()
        provenance = inherited.get("evidence_provenance") or config.get("SCENE2REAL_EVIDENCE_PROVENANCE") or provenance
        run_id, session_id, parent_run_id = (value or inherited.get(key) for key, value in
                                           (("run_id", run_id), ("session_id", session_id), ("parent_run_id", parent_run_id)))
        if not (run_id or session_id) or any(v and not _SAFE_ID.fullmatch(v) for v in (run_id, session_id, parent_run_id)):
            _STATE["dropped"] += 1
            return None
        event_id = uuid.uuid4().hex
        event = sanitize({**inherited, **attrs, "event_id": event_id, "stage": stage,
                          "run_id": run_id, "session_id": session_id, "parent_run_id": parent_run_id,
                          "trace_group_id": parent_run_id or run_id or session_id,
                          "source_commit": _SOURCE_COMMIT, "timestamp": datetime.now(timezone.utc).isoformat(),
                          "provenance": provenance if provenance in _PROVENANCE else "mocked",
                          "weave_status": config.TELEMETRY.get("weave", "skipped: not initialised")})
        directory = config.RUNS_DIR / (run_id if run_id else "live_" + session_id)
        _ensure_worker()
        _QUEUE.put_nowait((event, directory / "telemetry.jsonl"))
        _STATE["enqueued"] += 1
        return event_id
    except Exception:
        _STATE["dropped"] += 1
        return None


def status():
    return {**_STATE, "queue_size": _QUEUE.qsize(), "queue_capacity": _QUEUE.maxsize, "remote_queue_size": _REMOTE_QUEUE.qsize(),
            "weave": config.TELEMETRY.get("weave"), "delivery": "best effort; SDK submissions not remote acknowledgements"}


def flush(timeout=2):
    """Bounded drain for evaluation/shutdown; never call from a physics loop."""
    until = time.monotonic() + min(max(timeout, 0), 10)
    while (_QUEUE.unfinished_tasks or _REMOTE_QUEUE.unfinished_tasks) and time.monotonic() < until:
        time.sleep(.01)
    return _QUEUE.unfinished_tasks == 0 and _REMOTE_QUEUE.unfinished_tasks == 0
