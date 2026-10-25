import hashlib
import pytest
from fastapi.testclient import TestClient

from scene2real import config, pipeline
from scene2real.app import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "RUNS_DIR", tmp_path)
    monkeypatch.setattr(pipeline, "_RUNS", {})
    return TestClient(app)


def test_catalogue_adds_media_digest_without_changing_existing_fields(client):
    clips = client.get("/api/clips").json()
    assert len(clips) == 7
    for clip in clips:
        assert set(clip) == {"clip_id", "label", "filename", "duration_s", "media_sha256"}
        assert clip["media_sha256"] == hashlib.sha256((config.CLIPS_DIR / clip["filename"]).read_bytes()).hexdigest()
    assert all(set(c) == {"clip_id", "label", "filename", "duration_s"} for c in pipeline.list_clips())


def test_demo_video_get_head_range_and_etag(client):
    clip = client.get("/api/clips").json()[0]
    data = (config.CLIPS_DIR / clip["filename"]).read_bytes()
    etag = f'"{clip["media_sha256"]}"'

    full = client.get(f"/api/clips/{clip['clip_id']}/video")
    assert full.status_code == 200
    assert full.headers["content-type"] == "video/mp4"
    assert full.headers["etag"] == etag
    assert full.headers["accept-ranges"] == "bytes"
    assert full.headers["x-content-type-options"] == "nosniff"
    assert full.content == data and data[4:8] == b"ftyp"

    head = client.head(f"/api/clips/{clip['clip_id']}/video")
    assert head.status_code == 200
    assert int(head.headers["content-length"]) == len(data)
    assert head.content == b""

    part = client.get(f"/api/clips/{clip['clip_id']}/video", headers={"range": "bytes=4-7"})
    assert part.status_code == 206
    assert part.headers["content-range"] == f"bytes 4-7/{len(data)}"
    assert part.content == b"ftyp"

    unchanged = client.get(f"/api/clips/{clip['clip_id']}/video", headers={"if-none-match": etag})
    assert unchanged.status_code == 304
    assert unchanged.content == b""
    assert unchanged.headers["etag"] == etag

    changed = client.get(f"/api/clips/{clip['clip_id']}/video", headers={"if-none-match": '"stale"'})
    assert changed.status_code == 200


@pytest.mark.parametrize("clip_id", ["nope", "../README.md", "..%2f..%2fpyproject.toml", "%2e%2e%2fREADME.md", "clips.json", "demo_cctv_provenance.json", ".", ""])
def test_demo_video_serves_only_registered_clips(client, clip_id):
    response = client.get(f"/api/clips/{clip_id}/video")
    assert response.status_code == 404
    assert "video/mp4" not in response.headers.get("content-type", "")


def test_demo_video_rejects_registered_entry_that_escapes_clips_dir(client, monkeypatch):
    monkeypatch.setattr(pipeline, "list_clips", lambda: [{"clip_id": "escape", "label": "x", "filename": "../README.md", "duration_s": 1.0}])
    assert client.get("/api/clips/escape/video").status_code == 404
    assert client.get("/api/clips/escape/video").json()["detail"] == "demo clip unavailable"
