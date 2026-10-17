"""Video ingest works without system FFmpeg executables on PATH."""
import subprocess
from pathlib import Path

import pytest
from static_ffmpeg import run as portable

from scene2real import ingest


def test_video_ingest_without_system_tools(tmp_path, monkeypatch):
    ffmpeg, _ = portable.get_or_fetch_platform_executables_else_raise()
    clip = tmp_path / "clip.mp4"
    subprocess.run(
        [ffmpeg, "-v", "error", "-f", "lavfi", "-i", "testsrc=duration=2:size=320x240:rate=10",
         "-pix_fmt", "yuv420p", str(clip)],
        check=True,
    )
    monkeypatch.setenv("PATH", "")

    info = ingest.validate_clip(clip)
    assert info["duration_s"] == pytest.approx(2.0)
    assert len(info["sha256"]) == 64
    frames = ingest.extract_frames(clip, info["duration_s"], tmp_path / "frames")
    assert len(frames) == 5
    assert [f["t_s"] for f in frames] == [0.2, 0.6, 1.0, 1.4, 1.8]
    assert all(Path(f["path"]).read_bytes().startswith(b"\xff\xd8") for f in frames)

    invalid = tmp_path / "invalid.mp4"
    invalid.write_bytes(b"\x00\x00\x00\x18ftypisom" + b"\x00" * 32)
    with pytest.raises(ingest.IngestError, match="not a parseable video"):
        ingest.validate_clip(invalid)


def test_system_tools_preferred(monkeypatch):
    monkeypatch.setattr(ingest.shutil, "which", lambda name: f"/system/bin/{name}")

    def unexpected_download():
        pytest.fail("System tools must not trigger a portable binary download")

    monkeypatch.setattr(portable, "get_or_fetch_platform_executables_else_raise", unexpected_download)
    assert ingest.media_tool("ffprobe") == "/system/bin/ffprobe"
    assert ingest.media_tool("ffmpeg") == "/system/bin/ffmpeg"


def test_unavailable_tools_explain_setup(monkeypatch):
    monkeypatch.setenv("PATH", "")

    def unavailable():
        raise OSError("download unavailable")

    monkeypatch.setattr(portable, "get_or_fetch_platform_executables_else_raise", unavailable)
    with pytest.raises(ingest.IngestError, match="static_ffmpeg_paths"):
        ingest.probe(Path("clip.mp4"))


@pytest.mark.parametrize("error", [FileNotFoundError("ffmpeg missing"), subprocess.TimeoutExpired("ffmpeg", 60)])
def test_frame_process_failures_are_ingest_errors(tmp_path, monkeypatch, error):
    monkeypatch.setattr(ingest, "media_tool", lambda name: name)

    def fail(*args, **kwargs):
        raise error

    monkeypatch.setattr(ingest.subprocess, "run", fail)
    with pytest.raises(ingest.IngestError, match="Frame extraction failed"):
        ingest.extract_frames(tmp_path / "clip.mp4", 2.0, tmp_path / "frames")
