#!/usr/bin/env bash
set -euo pipefail

# The volume may be mounted as root. Hand only the application data paths to
# the unprivileged user, then run both services under that user.
if [[ $(id -u) == 0 ]]; then
  mkdir -p /data/runs /data/cache
  chown 10001:10001 /data
  chown -R 10001:10001 /data/runs /data/cache
  exec gosu 10001:10001 /bin/bash "$0"
fi

: "${SCENE2REAL_SITE_TOKEN:?SCENE2REAL_SITE_TOKEN is required}"
backend_port="${SCENE2REAL_BACKEND_PORT:-8090}"
ready_attempts="${SCENE2REAL_BACKEND_READY_ATTEMPTS:-120}"
ready_delay_s="${SCENE2REAL_BACKEND_READY_DELAY_S:-0.25}"

[[ "$backend_port" =~ ^[1-9][0-9]{0,4}$ ]] && (( backend_port <= 65535 )) || {
  echo "SCENE2REAL_BACKEND_PORT must be between 1 and 65535." >&2
  exit 2
}
[[ "$ready_attempts" =~ ^[1-9][0-9]*$ ]] || {
  echo "SCENE2REAL_BACKEND_READY_ATTEMPTS must be a positive integer." >&2
  exit 2
}
[[ "$ready_delay_s" =~ ^[0-9]+([.][0-9]+)?$ ]] || {
  echo "SCENE2REAL_BACKEND_READY_DELAY_S must be a non-negative number." >&2
  exit 2
}

export SCENE2REAL_PROXY_HOST=0.0.0.0
export SCENE2REAL_PROXY_PORT="${PORT:-10000}"
export SCENE2REAL_PROXY_UPSTREAM="http://127.0.0.1:${backend_port}"

uvicorn scene2real.app:app --host 127.0.0.1 --port "$backend_port" --workers 1 &
backend_pid=$!

shutdown() {
  trap - TERM INT
  for pid in "$backend_pid" "${proxy_pid:-}"; do
    [[ -n "$pid" ]] && kill -TERM "$pid" 2>/dev/null || true
  done
  for pid in "$backend_pid" "${proxy_pid:-}"; do
    [[ -n "$pid" ]] && wait "$pid" 2>/dev/null || true
  done
}
trap 'shutdown; exit 0' TERM INT

backend_ready=0
for ((attempt = 1; attempt <= ready_attempts; attempt += 1)); do
  if ! kill -0 "$backend_pid" 2>/dev/null; then
    set +e
    wait "$backend_pid"
    backend_status=$?
    set -e
    echo "Scene2Real backend exited before it became ready (status ${backend_status})." >&2
    [[ "$backend_status" -eq 0 ]] && backend_status=1
    exit "$backend_status"
  fi
  if python3 - "$backend_port" <<'PY'
import sys
from urllib.request import urlopen

try:
    with urlopen(f'http://127.0.0.1:{sys.argv[1]}/api/health', timeout=0.5) as response:
        raise SystemExit(0 if response.status == 200 else 1)
except Exception:
    raise SystemExit(1)
PY
  then
    backend_ready=1
    break
  fi
  sleep "$ready_delay_s"
done

if [[ "$backend_ready" != 1 ]]; then
  echo "Scene2Real backend did not become ready before the startup deadline." >&2
  shutdown
  exit 1
fi

echo "Scene2Real backend is ready; starting the authenticated proxy."
node /app/ops/site_api_proxy.mjs &
proxy_pid=$!

# A dead backend or proxy makes the whole container unhealthy so the hosting
# platform can restart it; do not leave the surviving process running alone.
set +e
wait -n "$backend_pid" "$proxy_pid"
status=$?
set -e
shutdown
if [[ $status -eq 0 ]]; then
  status=1
fi
exit "$status"
