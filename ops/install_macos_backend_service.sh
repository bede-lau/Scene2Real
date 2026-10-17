#!/bin/bash
set -euo pipefail

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "This installer is for macOS LaunchAgents." >&2
  exit 1
fi

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="$ROOT/.venv/bin/python"
UVICORN="$ROOT/.venv/bin/uvicorn"
LABEL="com.bedelau.scene2real.backend"
DOMAIN="gui/$(id -u)"
AGENTS="$HOME/Library/LaunchAgents"
LOGS="$HOME/Library/Logs/Scene2Real"
PLIST="$AGENTS/$LABEL.plist"
TEAM_CONFIG_PATH="${TEAM_CONFIG:-${XDG_CONFIG_HOME:-$HOME/.config}/scene2real/team.config}"

[[ -x "$PYTHON" && -x "$UVICORN" ]] || {
  echo "Create the project's .venv and install requirements.txt first." >&2
  exit 1
}
"$PYTHON" -c 'import fastapi, uvicorn'

mkdir -p "$AGENTS" "$LOGS"
umask 077
cat > "$PLIST" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>$UVICORN</string>
    <string>scene2real.app:app</string>
    <string>--host</string><string>127.0.0.1</string>
    <string>--port</string><string>8090</string>
  </array>
  <key>WorkingDirectory</key><string>$ROOT</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>HOME</key><string>$HOME</string>
    <key>TEAM_CONFIG</key><string>$TEAM_CONFIG_PATH</string>
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

if launchctl print "$DOMAIN/$LABEL" >/dev/null 2>&1; then
  launchctl bootout "$DOMAIN/$LABEL"
fi
launchctl bootstrap "$DOMAIN" "$PLIST"
launchctl kickstart -k "$DOMAIN/$LABEL"
echo "Installed $LABEL. Logs: $LOGS"
