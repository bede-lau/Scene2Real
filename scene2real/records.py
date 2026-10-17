"""Run persistence (local runs/<id>/run.json) and VAST S3 archive."""
import json
from pathlib import Path

from . import config


def run_dir(run_id):
    return config.RUNS_DIR / run_id


def save(run):
    d = run_dir(run["run_id"])
    d.mkdir(parents=True, exist_ok=True)
    tmp = d / "run.json.tmp"
    tmp.write_text(json.dumps(run, indent=1))
    tmp.replace(d / "run.json")


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
        if with_clip and run["clip_ref"].get("s3_uri") is None:
            s3.upload_file(str(d / "clip.mp4"), bucket, f"{prefix}/clip.mp4")
            run["clip_ref"]["s3_uri"] = f"s3://{bucket}/{prefix}/clip.mp4"
        for name in extra_files:
            if (d / name).exists():
                s3.upload_file(str(d / name), bucket, f"{prefix}/{name}")
        run.setdefault("telemetry", {})["vast"] = "ok"
        save(run)
        s3.put_object(Bucket=bucket, Key=f"{prefix}/run.json", Body=json.dumps(run, indent=1).encode())
        return "ok"
    except Exception as e:  # noqa: BLE001
        msg = f"skipped: {type(e).__name__}: {str(e)[:120]}"
        run.setdefault("telemetry", {})["vast"] = msg
        try:
            save(run)
        except Exception:  # noqa: BLE001
            pass
        return msg
