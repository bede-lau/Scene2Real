#!/usr/bin/env bash
# Run on the team VM: loads secrets from /config/team-28.config and starts the app.
set -euo pipefail
cd "$(dirname "$0")"
set -a; . /config/team-28.config; set +a
exec .venv/bin/uvicorn scene2real.app:app --host 127.0.0.1 --port 8090
