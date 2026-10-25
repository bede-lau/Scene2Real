import os
import socket
import stat
import subprocess
import sys
import textwrap
import time
from pathlib import Path

import pytest


SCRIPT = Path(__file__).parents[1] / "ops" / "run_container.sh"
pytestmark = pytest.mark.skipif(sys.platform != "linux", reason="Container entrypoint requires Linux Bash with wait -n")


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def write_executable(path, source):
    path.write_text(textwrap.dedent(source))
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


def wait_for(path, timeout=5):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if path.exists():
            return float(path.read_text())
        time.sleep(0.02)
    raise AssertionError(f"Timed out waiting for {path}")


@pytest.fixture
def startup_harness(tmp_path):
    commands = tmp_path / "commands"
    commands.mkdir()
    ready = tmp_path / "ready"
    node_started = tmp_path / "node-started"
    write_executable(
        commands / "id",
        """\
        #!/bin/sh
        if [ "$1" = "-u" ]; then echo 10001; exit 0; fi
        exec /usr/bin/id "$@"
        """,
    )
    write_executable(
        commands / "node",
        """\
        #!/usr/bin/env python3
        import os, signal, time
        from pathlib import Path
        Path(os.environ['TEST_NODE_STARTED']).write_text(str(time.time()))
        signal.signal(signal.SIGTERM, lambda *_: exit(0))
        signal.signal(signal.SIGINT, lambda *_: exit(0))
        while True: time.sleep(1)
        """,
    )
    write_executable(
        commands / "uvicorn",
        """\
        #!/usr/bin/env python3
        import os, signal, sys, time
        from http.server import BaseHTTPRequestHandler, HTTPServer
        from pathlib import Path

        mode = os.environ['TEST_UVICORN_MODE']
        if mode in {'exit', 'exit_zero'}:
            raise SystemExit(0 if mode == 'exit_zero' else 23)
        if mode == 'never':
            signal.signal(signal.SIGTERM, lambda *_: exit(0))
            signal.signal(signal.SIGINT, lambda *_: exit(0))
            while True: time.sleep(1)
        port = int(sys.argv[sys.argv.index('--port') + 1])
        time.sleep(float(os.environ.get('TEST_READY_DELAY_S', '0')))
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200 if self.path == '/api/health' else 404)
                self.end_headers()
            def log_message(self, *_): pass
        server = HTTPServer(('127.0.0.1', port), Handler)
        Path(os.environ['TEST_READY_MARKER']).write_text(str(time.time()))
        signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
        signal.signal(signal.SIGINT, lambda *_: sys.exit(0))
        server.serve_forever()
        """,
    )
    environment = os.environ | {
        "PATH": f"{commands}{os.pathsep}{os.environ['PATH']}",
        "SCENE2REAL_SITE_TOKEN": "a" * 32,
        "SCENE2REAL_BACKEND_PORT": str(free_port()),
        "SCENE2REAL_BACKEND_READY_ATTEMPTS": "80",
        "SCENE2REAL_BACKEND_READY_DELAY_S": "0.02",
        "TEST_NODE_STARTED": str(node_started),
        "TEST_READY_MARKER": str(ready),
    }
    return environment, ready, node_started


def test_container_waits_for_local_api_before_exposing_proxy(startup_harness):
    environment, ready, node_started = startup_harness
    environment |= {"TEST_UVICORN_MODE": "ready", "TEST_READY_DELAY_S": "0.2"}
    process = subprocess.Popen(["bash", str(SCRIPT)], env=environment, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        ready_at = wait_for(ready)
        try:
            node_at = wait_for(node_started)
        except AssertionError:
            process.terminate()
            stdout, stderr = process.communicate(timeout=5)
            pytest.fail(f"Proxy did not start after readiness:\nstdout={stdout}\nstderr={stderr}")
        assert node_at >= ready_at
        assert process.poll() is None
    finally:
        process.terminate()
        process.wait(timeout=5)


@pytest.mark.parametrize("mode", ["exit", "exit_zero", "never"])
def test_container_never_exposes_proxy_when_backend_cannot_be_ready(startup_harness, mode):
    environment, _, node_started = startup_harness
    environment |= {"TEST_UVICORN_MODE": mode}
    if mode == "never":
        environment |= {"SCENE2REAL_BACKEND_READY_ATTEMPTS": "3", "SCENE2REAL_BACKEND_READY_DELAY_S": "0.02"}
    result = subprocess.run(["bash", str(SCRIPT)], env=environment, capture_output=True, text=True, timeout=5)
    assert result.returncode != 0
    assert not node_started.exists()
    if mode in {"exit", "exit_zero"}:
        assert "exited before it became ready" in result.stderr
    else:
        assert "did not become ready" in result.stderr
