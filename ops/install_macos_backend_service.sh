#!/bin/bash
set -euo pipefail

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "This installer is for macOS LaunchAgents." >&2
  exit 1
fi

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LABEL="com.bedelau.scene2real.backend"
DOMAIN="gui/$(id -u)"
AGENTS="$HOME/Library/LaunchAgents"
LOGS="$HOME/Library/Logs/Scene2Real"
SERVICE_ROOT="$HOME/Library/Application Support/Scene2Real"
APP_ROOT="$SERVICE_ROOT/app"
SITE_PACKAGES="$SERVICE_ROOT/site-packages"
PLIST="$AGENTS/$LABEL.plist"
TEAM_CONFIG_PATH="${TEAM_CONFIG:-${XDG_CONFIG_HOME:-$HOME/.config}/scene2real/team.config}"

[[ -x "$ROOT/.venv/bin/python" ]] || {
  echo "Create the project's .venv and install requirements.txt first." >&2
  exit 1
}

umask 077
mkdir -p "$AGENTS" "$LOGS" "$APP_ROOT"
BASE_PYTHON="$("$ROOT/.venv/bin/python" -c 'import sys; print(sys._base_executable)')"
PYTHON_MINOR="$("$ROOT/.venv/bin/python" -c 'import sys; print(f"python{sys.version_info.major}.{sys.version_info.minor}")')"
SITE_SOURCE="$ROOT/.venv/lib/$PYTHON_MINOR/site-packages"
[[ -x "$BASE_PYTHON" && -d "$SITE_SOURCE" ]] || {
  echo "Could not find the project's Python runtime and installed packages." >&2
  exit 1
}

# launchd cannot read checkouts under macOS-protected Desktop/Documents folders.
# Run a private snapshot from Application Support instead of granting broad disk access.
if launchctl print "$DOMAIN/$LABEL" >/dev/null 2>&1; then
  launchctl bootout "$DOMAIN/$LABEL"
fi
rsync -a --delete "$SITE_SOURCE/" "$SITE_PACKAGES/"
PYTHONPATH="$SITE_PACKAGES" "$BASE_PYTHON" -c 'import fastapi, uvicorn'
for directory in scene2real static clips assets; do
  rsync -a --delete "$ROOT/$directory/" "$APP_ROOT/$directory/"
done
if [[ ! -d "$APP_ROOT/runs" ]]; then
  mkdir -p "$APP_ROOT/runs"
  rsync -a "$ROOT/runs/" "$APP_ROOT/runs/"
fi
mkdir -p "$APP_ROOT/cache"
rm -rf "$SERVICE_ROOT/venv" # obsolete copy created by the earlier installer revision
chmod -R go-rwx "$SERVICE_ROOT"

cat > "$PLIST" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>$BASE_PYTHON</string>
    <string>-m</string>
    <string>uvicorn</string>
    <string>scene2real.app:app</string>
    <string>--host</string><string>127.0.0.1</string>
    <string>--port</string><string>8090</string>
  </array>
  <key>WorkingDirectory</key><string>$APP_ROOT</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>HOME</key><string>$HOME</string>
    <key>TEAM_CONFIG</key><string>$TEAM_CONFIG_PATH</string>
    <key>PYTHONPATH</key><string>$SITE_PACKAGES</string>
    <key>PATH</key><string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
    <key>PYTHONUNBUFFERED</key><string>1</string>
  </dict>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>ThrottleInterval</key><integer>10</integer>
  <key>ProcessType</key><string>Background</string>
  <key>StandardOutPath</key><string>$LOGS/backend.log</string>
  <key>StandardErrorPath</key><string>$LOGS/backend-error.log</string>
</dict>
</plist>
PLIST
chmod 600 "$PLIST"

launchctl bootstrap "$DOMAIN" "$PLIST"
launchctl kickstart -k "$DOMAIN/$LABEL"
for attempt in $(seq 1 30); do
  if curl --silent --show-error --fail --max-time 2 http://127.0.0.1:8090/api/clips >/dev/null 2>&1; then
    echo "Installed $LABEL from $APP_ROOT. Logs: $LOGS"
    exit 0
  fi
  sleep 1
done
echo "Backend did not become healthy. Check $LOGS/backend-error.log." >&2
exit 1
