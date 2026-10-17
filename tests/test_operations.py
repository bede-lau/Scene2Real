import json
import threading
import time

import pytest
from fastapi.testclient import TestClient

from scene2real import config, pipeline, records
from scene2real.app import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "RUNS_DIR", tmp_path)
    monkeypatch.setattr(pipeline, "_RUNS", {})
    records.save({"run_id": "test-run", "state": "uploaded"})
    return TestClient(app)


def wait_status(client, url, status):
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        data = client.get(url).json()
        if data["status"] == status:
            return data
        time.sleep(0.01)
    pytest.fail(f"operation did not reach {status}: {data}")


def test_background_operation_polling_duplicate_and_run_result(client, monkeypatch):
    started, release = threading.Event(), threading.Event()

    def analyse(run_id):
        started.set()
        assert release.wait(3)
        return {"run_id": run_id, "state": "analysed"}

    monkeypatch.setattr(pipeline, "analyse", analyse)
    base = "/api/runs/test-run/operations"
    response = client.post(base, json={"operation": "analyse"})
    assert response.status_code == 202
    job = response.json()
    assert job["status"] == "pending"
    assert started.wait(2)
    url = f"{base}/{job['id']}"
    assert client.get(url).json()["status"] == "running"
    assert client.get(base).json()["id"] == job["id"]
    assert client.post(base, json={"operation": "analyse"}).json()["id"] == job["id"]
    assert client.post(base, json={"operation": "scene"}).status_code == 409
    release.set()
    done = wait_status(client, url, "completed")
    assert done["result"] == {"run_id": "test-run", "state": "analysed"}


def test_failure_status_and_retry(client, monkeypatch):
    def fail(_):
        raise pipeline.PipelineError(409, "Cannot analyse in this state", False)

    monkeypatch.setattr(pipeline, "analyse", fail)
    base = "/api/runs/test-run/operations"
    job = client.post(base, json={"operation": "analyse"}).json()
    failed = wait_status(client, f"{base}/{job['id']}", "failed")
    assert failed["error"] == {"detail": "Cannot analyse in this state", "retryable": False, "status": 409}
    monkeypatch.setattr(pipeline, "analyse", lambda run_id: {"run_id": run_id, "state": "failed", "error": {"stage": "analyse"}})
    next_job = client.post(base, json={"operation": "analyse"}).json()
    assert next_job["id"] != job["id"]
    # A handled pipeline failure is part of the normal run result.
    assert wait_status(client, f"{base}/{next_job['id']}", "completed")["result"]["state"] == "failed"
    assert client.get(f"{base}/{job['id']}").status_code == 404


def test_interrupted_and_invalid_jobs(client):
    base = "/api/runs/test-run/operations"
    assert client.get(base).status_code == 404
    assert client.post(base, json={"operation": "invalid"}).status_code == 422
    assert client.post("/api/runs/missing/operations", json={"operation": "analyse"}).status_code == 404
    path = config.RUNS_DIR / "test-run" / "operation.json"
    path.write_text(json.dumps({"id": "old", "run_id": "test-run", "operation": "analyse", "status": "running"}))
    job = client.get(base).json()
    assert job["status"] == "failed" and job["error"]["retryable"]
    assert json.loads(path.read_text())["status"] == "failed"


@pytest.mark.parametrize(("operation", "function"), [("scene", "build_scene"), ("run", "run_sim")])
def test_other_long_stages(client, monkeypatch, operation, function):
    monkeypatch.setattr(pipeline, function, lambda run_id: {"run_id": run_id, "stage": operation})
    base = "/api/runs/test-run/operations"
    job = client.post(base, json={"operation": operation}).json()
    assert wait_status(client, f"{base}/{job['id']}", "completed")["result"]["stage"] == operation


def test_unexpected_error_does_not_expose_exception(client, monkeypatch):
    def fail(_):
        raise RuntimeError("sensitive upstream detail")

    monkeypatch.setattr(pipeline, "analyse", fail)
    base = "/api/runs/test-run/operations"
    job = client.post(base, json={"operation": "analyse"}).json()
    result = wait_status(client, f"{base}/{job['id']}", "failed")
    assert result["error"]["status"] == 500
    assert "sensitive" not in json.dumps(result)
