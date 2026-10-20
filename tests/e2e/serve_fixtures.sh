#!/usr/bin/env bash
# Fixture-only server for the incident-summary browser checks. No model calls.
set -euo pipefail
cd "$(dirname "$0")/../.."
dest="$(mktemp -d "${TMPDIR:-/tmp}/s2r-report.XXXXXX")"
cp -R tests/fixtures/report_runs/. "$dest/"
export SCENE2REAL_RUNS_DIR="$dest"
export SCENE2REAL_SPATIAL_REVIEW=0
export SCENE2REAL_USE_CACHE=0
if [[ -x .venv/bin/uvicorn ]]; then
  uvicorn=.venv/bin/uvicorn
elif [[ -x ../.venv/bin/uvicorn ]]; then
  uvicorn=../.venv/bin/uvicorn
else
  echo "uvicorn not found in .venv or ../.venv" >&2
  exit 1
fi
exec "$uvicorn" scene2real.app:app --host 127.0.0.1 --port "${PORT:-8091}"
