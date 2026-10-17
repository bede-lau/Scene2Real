"""Run persistence (local runs/<id>/run.json) and VAST S3 archive."""
import json
from pathlib import Path

from . import config, observability


def run_dir(run_id):
    return config.RUNS_DIR / run_id


def save(run):
    d = run_dir(run["run_id"])
    d.mkdir(parents=True, exist_ok=True)
    tmp = d / "run.json.tmp"
    tmp.write_text(json.dumps(run, indent=1))
    tmp.replace(d / "run.json")


def evidence(run_id, label, value):
    """Immutable sanitized JSON artifact; safe to reference from linked telemetry."""
    payload = observability.sanitize(value, max_string=None, max_items=None)
    sha = observability.digest(payload)
    name = f"evidence/{label}_{sha}.json"
    path = run_dir(run_id) / name
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_text(json.dumps(payload, sort_keys=True, allow_nan=False))
        return {"path": f"runs/{run_id}/{name}", "sha256": sha}
    except OSError as exc:
        return {"status": "skipped", "error_type": type(exc).__name__, "sha256": sha}


def load(run_id):
    p = run_dir(run_id) / "run.json"
    if not p.exists():
        return None
    return json.loads(p.read_text())


def _client():
    import boto3
    from botocore.config import Config
    import urllib3
    urllib3.disable_warnings()
    return boto3.client("s3", endpoint_url=config.get("S3_ENDPOINT"), verify=False,
                        aws_access_key_id=config.get("ACCESS_KEY"), aws_secret_access_key=config.get("SECRET_KEY"),
                        config=Config(connect_timeout=5, read_timeout=30, retries={"max_attempts": 1}))


def archive(run, with_clip=False, extra_files=()):
    """Best effort. Returns 'ok' or 'skipped: reason'; sets run['telemetry']['vast'] and clip_ref.s3_uri."""
    try:
        bucket = config.get("S3_CHUNKS_BUCKET")
        if not (bucket and config.get("S3_ENDPOINT")):
            raise RuntimeError("S3 config missing")
        s3 = _client()
        prefix = f"scene2real/runs/{run['run_id']}"
        d = run_dir(run["run_id"])
        if with_clip:
            refs = run.get("video_refs") or [dict(run["clip_ref"], view_id="V1")]
            for ref in refs:
                view_id = ref["view_id"]
                name = "clip.mp4" if view_id == "V1" else f"clip_{view_id}.mp4"
                if ref.get("s3_uri") is None:
                    s3.upload_file(str(d / name), bucket, f"{prefix}/{name}")
                    ref["s3_uri"] = f"s3://{bucket}/{prefix}/{name}"
            run["clip_ref"]["s3_uri"] = refs[0]["s3_uri"]
        # Keep local correlated evidence and its immutable stage snapshots in VAST.
        evidence_files = [str(p.relative_to(d)) for p in (d / "evidence").glob("*.json")]
        observability.flush(.25)
        if (d / "telemetry.jsonl").exists():
            evidence_files.append("telemetry.jsonl")
        for name in dict.fromkeys([*extra_files, *evidence_files]):
            if (d / name).exists():
                s3.upload_file(str(d / name), bucket, f"{prefix}/{name}")
        run.setdefault("telemetry", {})["vast"] = "ok"
        save(run)
        s3.put_object(Bucket=bucket, Key=f"{prefix}/run.json", Body=json.dumps(run, indent=1).encode())
        observability.emit("archive", run_id=run["run_id"], provenance="deterministic",
                           outcome="ok", archive_prefix=f"s3://{bucket}/{prefix}")
        return "ok"
    except Exception as e:  # noqa: BLE001
        msg = observability.sanitize(f"skipped: {type(e).__name__}: {str(e)[:120]}")
        observability.emit("archive", run_id=run["run_id"], provenance="deterministic",
                           outcome="skipped", error_type=type(e).__name__)
        run.setdefault("telemetry", {})["vast"] = msg
        try:
            save(run)
        except Exception:  # noqa: BLE001
            pass
        return msg
