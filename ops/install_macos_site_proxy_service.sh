#!/bin/bash
set -euo pipefail

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "This installer is for macOS LaunchAgents." >&2
  exit 1
fi

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LABEL="com.bedelau.scene2real.site-proxy"
DOMAIN="gui/$(id -u)"
AGENTS="$HOME/Library/LaunchAgents"
LOGS="$HOME/Library/Logs/Scene2Real"
SERVICE_ROOT="$HOME/Library/Application Support/Scene2Real"
SERVICE_SCRIPT="$SERVICE_ROOT/site_api_proxy.mjs"
RUNNER="$SERVICE_ROOT/run_site_api_proxy.sh"
PLIST="$AGENTS/$LABEL.plist"
TOKEN_FILE="${SCENE2REAL_SITE_TOKEN_FILE:-${XDG_CONFIG_HOME:-$HOME/.config}/scene2real/site-proxy.env}"

NODE_BIN="$(command -v node || true)"
if [[ -z "$NODE_BIN" ]]; then
  for candidate in "$HOME/.local/bin/node" /opt/homebrew/bin/node /usr/local/bin/node; do
    if [[ -x "$candidate" ]]; then NODE_BIN="$candidate"; break; fi
  done
fi
[[ -n "$NODE_BIN" && -x "$NODE_BIN" ]] || {
  echo "Node.js is required to run the Site API proxy." >&2
  exit 1
}
[[ -f "$ROOT/ops/site_api_proxy.mjs" ]] || {
  echo "Missing ops/site_api_proxy.mjs." >&2
  exit 1
}
[[ -f "$TOKEN_FILE" ]] || {
  echo "Create the private Site proxy token file at $TOKEN_FILE first." >&2
  exit 1
}
TOKEN="$(sed -n 's/^SCENE2REAL_SITE_TOKEN=//p' "$TOKEN_FILE" | head -n 1 | tr -d '\r\n')"
[[ "$TOKEN" =~ ^[A-Za-z0-9_-]{32,}$ ]] || {
  echo "The Site proxy token file must contain one SCENE2REAL_SITE_TOKEN with at least 32 safe characters." >&2
  exit 1
}
unset TOKEN

umask 077
mkdir -p "$AGENTS" "$LOGS" "$SERVICE_ROOT"
install -m 600 "$ROOT/ops/site_api_proxy.mjs" "$SERVICE_SCRIPT"
cat > "$RUNNER" <<RUNNER
#!/bin/bash
set -euo pipefail
IFS='=' read -r key value < "$TOKEN_FILE"
[[ "\$key" == "SCENE2REAL_SITE_TOKEN" && "\$value" =~ ^[A-Za-z0-9_-]{32,}$ ]] || exit 1
export SCENE2REAL_SITE_TOKEN="\$value"
exec "$NODE_BIN" "$SERVICE_SCRIPT"
RUNNER
chmod 700 "$RUNNER"
chmod 600 "$TOKEN_FILE"

cat > "$PLIST" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array><string>$RUNNER</string></array>
  <key>WorkingDirectory</key><string>$SERVICE_ROOT</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>HOME</key><string>$HOME</string>
    <key>PATH</key><string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
    <key>SCENE2REAL_PROXY_PORT</key><string>8091</string>
    <key>SCENE2REAL_PROXY_UPSTREAM</key><string>http://127.0.0.1:8090</string>
  </dict>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>ThrottleInterval</key><integer>10</integer>
  <key>ProcessType</key><string>Background</string>
  <key>StandardOutPath</key><string>$LOGS/site-proxy.log</string>
  <key>StandardErrorPath</key><string>$LOGS/site-proxy-error.log</string>
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
  status="$(curl --silent --output /dev/null --write-out '%{http_code}' --max-time 2 http://127.0.0.1:8091/api/clips || true)"
  if [[ "$status" == "401" ]]; then
    echo "Installed $LABEL; the proxy is listening and rejects unauthenticated requests. Logs: $LOGS"
    exit 0
  fi
  sleep 1
done
echo "Site API proxy did not become healthy. Check $LOGS/site-proxy-error.log." >&2
exit 1
