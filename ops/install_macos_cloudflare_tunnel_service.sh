#!/bin/bash
set -euo pipefail

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "This installer is for macOS LaunchAgents." >&2
  exit 1
fi

LABEL="com.bedelau.scene2real.tunnel"
DOMAIN="gui/$(id -u)"
AGENTS="$HOME/Library/LaunchAgents"
LOGS="$HOME/Library/Logs/Scene2Real"
TUNNEL_NAME="${SCENE2REAL_TUNNEL_NAME:-scene2real-api}"
CONFIG="${SCENE2REAL_TUNNEL_CONFIG:-$HOME/.cloudflared/scene2real-api.yml}"
PLIST="$AGENTS/$LABEL.plist"

CLOUDFLARED_BIN="$(command -v cloudflared || true)"
if [[ -z "$CLOUDFLARED_BIN" ]]; then
  for candidate in "$HOME/.local/bin/cloudflared" /opt/homebrew/bin/cloudflared /usr/local/bin/cloudflared; do
    if [[ -x "$candidate" ]]; then CLOUDFLARED_BIN="$candidate"; break; fi
  done
fi
[[ -n "$CLOUDFLARED_BIN" && -x "$CLOUDFLARED_BIN" ]] || {
  echo "Install cloudflared before installing the tunnel service." >&2
  exit 1
}
[[ -f "$CONFIG" ]] || {
  echo "Create a named-tunnel config at $CONFIG first." >&2
  exit 1
}
grep -Eq '^tunnel:[[:space:]]*[^[:space:]]+' "$CONFIG" || {
  echo "Tunnel config is missing its tunnel ID." >&2
  exit 1
}
CREDENTIALS_FILE="$(sed -n 's/^credentials-file:[[:space:]]*//p' "$CONFIG" | head -n 1 | tr -d '\"' | tr -d "'" | tr -d '\r')"
[[ -n "$CREDENTIALS_FILE" ]] || {
  echo "Tunnel config is missing credentials-file." >&2
  exit 1
}
if [[ "$CREDENTIALS_FILE" != /* ]]; then
  CREDENTIALS_FILE="$(cd "$(dirname "$CONFIG")" && pwd)/$CREDENTIALS_FILE"
fi
[[ -f "$CREDENTIALS_FILE" ]] || {
  echo "The named-tunnel credentials file is missing." >&2
  exit 1
}
grep -Fq 'hostname: scene2real-api.thecosmoslabs.com' "$CONFIG" || {
  echo "Tunnel config must route scene2real-api.thecosmoslabs.com." >&2
  exit 1
}
grep -Fq 'service: http://127.0.0.1:8091' "$CONFIG" || {
  echo "Tunnel config must forward to the authenticated loopback proxy on port 8091." >&2
  exit 1
}

umask 077
mkdir -p "$AGENTS" "$LOGS"
chmod 600 "$CONFIG" "$CREDENTIALS_FILE"
"$CLOUDFLARED_BIN" tunnel --config "$CONFIG" ingress validate >/dev/null

cat > "$PLIST" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>$CLOUDFLARED_BIN</string>
    <string>tunnel</string><string>--config</string><string>$CONFIG</string>
    <string>run</string><string>$TUNNEL_NAME</string>
  </array>
  <key>WorkingDirectory</key><string>$HOME</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>HOME</key><string>$HOME</string>
    <key>PATH</key><string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
  </dict>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>ThrottleInterval</key><integer>10</integer>
  <key>ProcessType</key><string>Background</string>
  <key>StandardOutPath</key><string>$LOGS/tunnel.log</string>
  <key>StandardErrorPath</key><string>$LOGS/tunnel-error.log</string>
</dict>
</plist>
PLIST
chmod 600 "$PLIST"

if launchctl print "$DOMAIN/$LABEL" >/dev/null 2>&1; then
  launchctl bootout "$DOMAIN/$LABEL"
fi
launchctl bootstrap "$DOMAIN" "$PLIST"
launchctl kickstart -k "$DOMAIN/$LABEL"
for attempt in $(seq 1 30); do
  if launchctl print "$DOMAIN/$LABEL" 2>/dev/null | grep -q 'state = running'; then
    echo "Installed $LABEL. launchd will restart cloudflared after crashes and login. Logs: $LOGS"
    exit 0
  fi
  sleep 1
done
echo "Cloudflare Tunnel did not start. Check $LOGS/tunnel-error.log." >&2
exit 1
