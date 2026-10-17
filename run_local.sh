#!/usr/bin/env bash
# Keep local credentials outside the checkout; TEAM_CONFIG can override the path.
set -euo pipefail
cd "$(dirname "$0")"
export TEAM_CONFIG="${TEAM_CONFIG:-${XDG_CONFIG_HOME:-$HOME/.config}/scene2real/team.config}"
exec .venv/bin/uvicorn scene2real.app:app --host 127.0.0.1 --port 8090
