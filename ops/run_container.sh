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
export SCENE2REAL_PROXY_HOST=0.0.0.0
export SCENE2REAL_PROXY_PORT="${PORT:-10000}"

uvicorn scene2real.app:app --host 127.0.0.1 --port 8090 --workers 1 &
backend_pid=$!
node /app/ops/site_api_proxy.mjs &
proxy_pid=$!

shutdown() {
  trap - TERM INT
  kill -TERM "$backend_pid" "$proxy_pid" 2>/dev/null || true
  wait "$backend_pid" 2>/dev/null || true
  wait "$proxy_pid" 2>/dev/null || true
}
trap 'shutdown; exit 0' TERM INT

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
