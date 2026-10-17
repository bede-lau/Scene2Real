"""Clip ingest: validate, hash, probe, extract evenly spaced frames."""
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

from . import config


class IngestError(Exception):
    pass


def media_tool(name: str) -> str:
    """Use system FFmpeg tools, or the portable binaries in our Python environment."""
    installed = shutil.which(name)
    if installed:
        return installed
    try:
        from static_ffmpeg.run import get_or_fetch_platform_executables_else_raise

        ffmpeg, ffprobe = get_or_fetch_platform_executables_else_raise()
        return {"ffmpeg": ffmpeg, "ffprobe": ffprobe}[name]
    except Exception as e:
        raise IngestError(
            f"{name} is unavailable. Install requirements.txt and run "
            "'.venv/bin/static_ffmpeg_paths' to prepare the video tools, "
            "or install FFmpeg on the server."
        ) from e


def probe(path: Path) -> dict:
    ffprobe = media_tool("ffprobe")
    try:
        r = subprocess.run(
            [ffprobe, "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)],
            capture_output=True, text=True, timeout=30)
        info = json.loads(r.stdout or "{}")
    except Exception as e:  # noqa: BLE001
        raise IngestError(f"ffprobe failed: {e}") from e
    if r.returncode != 0 or "format" not in info:
        raise IngestError("File is not a parseable video")
    if not any(s.get("codec_type") == "video" for s in info.get("streams", [])):
        raise IngestError("No video stream found")
    try:
        dur = float(info["format"]["duration"])
    except (KeyError, ValueError):
        raise IngestError("Cannot determine clip duration")
    return {"duration_s": dur}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def validate_clip(path: Path) -> dict:
    """Validate a stored file; returns {sha256, duration_s}. Raises IngestError."""
    size = path.stat().st_size
    if size == 0:
        raise IngestError("Empty file")
    if size > config.MAX_UPLOAD_BYTES:
        raise IngestError("File exceeds 200 MB limit")
    head = path.read_bytes()[:16] if size >= 16 else b""
    if head[4:8] != b"ftyp":
        raise IngestError("Not an mp4/quicktime file (missing ftyp box)")
    dur = probe(path)["duration_s"]
    if not (config.MIN_DURATION_S <= dur <= config.MAX_DURATION_S):
        raise IngestError(f"Clip duration {dur:.1f}s outside allowed {config.MIN_DURATION_S:.0f}-{config.MAX_DURATION_S:.0f}s")
    return {"sha256": sha256_file(path), "duration_s": round(dur, 3)}


def extract_frames(clip: Path, duration_s: float, out_dir: Path, n: int = config.N_FRAMES) -> list[dict]:
    """n evenly spaced JPEG frames (640 px wide). Returns [{t_s, path}]."""
    ffmpeg = media_tool("ffmpeg")
    out_dir.mkdir(parents=True, exist_ok=True)
    frames = []
    for k in range(n):
        t = round(duration_s * (k + 0.5) / n, 2)
        p = out_dir / f"frame_{k:02d}.jpg"
        try:
            r = subprocess.run(
                [ffmpeg, "-v", "error", "-y", "-ss", f"{t}", "-i", str(clip), "-frames:v", "1",
                 "-vf", "scale=640:-2", "-q:v", "4", str(p)],
                capture_output=True, text=True, timeout=60)
        except (OSError, subprocess.TimeoutExpired) as e:
            raise IngestError(f"Frame extraction failed at t={t}s: {e}") from e
        if r.returncode != 0 or not p.exists() or p.stat().st_size == 0:
            raise IngestError(f"Frame extraction failed at t={t}s: {r.stderr[-200:]}")
        frames.append({"t_s": t, "path": str(p)})
    return frames
