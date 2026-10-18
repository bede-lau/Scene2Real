#!/usr/bin/env bash
set -euo pipefail

# Install dedicated system services without touching the team's existing apps.
[[ "$(uname -s)" == Linux && -d /run/systemd/system ]] || { echo 'Linux with systemd is required.' >&2; exit 1; }
[[ "$(id -u)" -ne 0 ]] || { echo 'Run this installer as the application user, not root.' >&2; exit 1; }
command -v systemctl >/dev/null && command -v sudo >/dev/null || { echo 'systemctl and sudo are required.' >&2; exit 1; }
sudo -n true || { echo 'Non-interactive sudo access is required.' >&2; exit 1; }

root="$(cd "$(dirname "$0")/.." && pwd -P)"
user="$(id -un)"
group="$(id -gn)"
[[ "$user" =~ ^[a-zA-Z0-9_-]+$ ]] || { echo 'The application user name is unsupported for service naming.' >&2; exit 1; }
backend_service="scene2real-${user}-backend.service"
proxy_service="scene2real-${user}-site-proxy.service"
tunnel_service="scene2real-${user}-tunnel.service"
python="$root/.venv/bin/python"
node="$(command -v node || true)"
team_config="${TEAM_CONFIG:-/config/team-28.config}"
config_dir="${XDG_CONFIG_HOME:-$HOME/.config}/scene2real"
backend_env="$config_dir/backend.env"
proxy_env="$config_dir/site-proxy.env"
runs_dir="${XDG_DATA_HOME:-$HOME/.local/share}/scene2real/runs"
backend_port="${SCENE2REAL_BACKEND_PORT:-18090}"
proxy_port="${SCENE2REAL_PROXY_PORT:-18091}"
tunnel_config="${SCENE2REAL_TUNNEL_CONFIG:-}"

safe_unit_value() {
  [[ "$1" != *$'\n'* && "$1" != *$'\r'* && "$1" != *'"'* && "$1" != *'\'* && "$1" != *'%'* ]]
}
for value in "$root" "$HOME" "$user" "$group" "$team_config" "$backend_env" "$proxy_env" "$runs_dir" "$node" "$tunnel_config"; do
  safe_unit_value "$value" || { echo 'A path or user name contains characters unsupported by this installer.' >&2; exit 1; }
done
for port in "$backend_port" "$proxy_port"; do
  [[ "$port" =~ ^[0-9]{1,5}$ ]] && (( 10#$port >= 1024 && 10#$port <= 65535 )) || { echo 'Service ports must be between 1024 and 65535.' >&2; exit 1; }
done
(( 10#$backend_port != 10#$proxy_port )) || { echo 'Backend and proxy ports must differ.' >&2; exit 1; }
[[ -x "$python" && -x "$node" && -f "$root/ops/site_api_proxy.mjs" ]] || { echo 'The existing .venv, Node, or proxy script is missing.' >&2; exit 1; }
"$python" -c 'import fastapi, uvicorn' || { echo 'Install backend dependencies in the existing .venv first.' >&2; exit 1; }
"$node" -e 'process.exit(Number(process.versions.node.split(".")[0]) >= 18 ? 0 : 1)' || { echo 'Node 18 or newer is required.' >&2; exit 1; }
[[ -f "$team_config" && -r "$team_config" ]] || { echo 'The team configuration file is missing or unreadable.' >&2; exit 1; }

private_file() {
  [[ -f "$1" && ! -L "$1" && "$(stat -c %u "$1")" == "$(id -u)" && "$(stat -c %a "$1")" == 600 ]]
}
private_file "$proxy_env" || { echo 'The proxy token file must be owned by the application user and have mode 600.' >&2; exit 1; }
awk 'BEGIN { n=0; ok=0 } /^SCENE2REAL_SITE_TOKEN=/ { n++; v=substr($0,23); if (length(v)>=32 && v ~ /^[A-Za-z0-9_-]+$/) ok=1 } END { exit !(n==1 && ok) }' "$proxy_env" || { echo 'The proxy token file must contain exactly one valid token of at least 32 characters.' >&2; exit 1; }
if [[ -e "$backend_env" ]]; then
  private_file "$backend_env" || { echo 'backend.env must be owned by the application user and have mode 600.' >&2; exit 1; }
fi

cloudflared=''
if [[ -n "$tunnel_config" ]]; then
  cloudflared="$(command -v cloudflared || true)"
  [[ -x "$cloudflared" && -f "$tunnel_config" && -r "$tunnel_config" ]] || { echo 'A readable tunnel config and cloudflared are required.' >&2; exit 1; }
  safe_unit_value "$cloudflared" || { echo 'The cloudflared path contains unsupported characters.' >&2; exit 1; }
  credentials="$(sed -n 's/^[[:space:]]*credentials-file:[[:space:]]*//p' "$tunnel_config" | head -n 1 | tr -d "\"'\r")"
  [[ -n "$credentials" ]] || { echo 'Tunnel config must specify a credentials file.' >&2; exit 1; }
  [[ "$credentials" == /* ]] || credentials="$(dirname "$tunnel_config")/$credentials"
  private_file "$credentials" || { echo 'Tunnel credentials must be owned by the application user and have mode 600.' >&2; exit 1; }
  grep -Eq "^[[:space:]]*(-[[:space:]]*)?service:[[:space:]]*http://127[.]0[.]0[.]1:${proxy_port}[[:space:]]*$" "$tunnel_config" || { echo 'Tunnel config must route to the selected loopback proxy port.' >&2; exit 1; }
  if grep -E '^[[:space:]]*(-[[:space:]]*)?service:[[:space:]]*https?://' "$tunnel_config" | grep -Ev "^[[:space:]]*(-[[:space:]]*)?service:[[:space:]]*http://127[.]0[.]0[.]1:${proxy_port}[[:space:]]*$" >/dev/null; then
    echo 'Tunnel config must not forward HTTP traffic to other services.' >&2; exit 1
  fi
  "$cloudflared" tunnel --config "$tunnel_config" ingress validate >/dev/null || { echo 'Tunnel ingress validation failed.' >&2; exit 1; }
fi

# Never overwrite a service that was not installed for this user and checkout.
services=("$backend_service" "$proxy_service")
[[ -z "$tunnel_config" ]] || services+=("$tunnel_service")
for service in "${services[@]}"; do
  unit_path="/etc/systemd/system/$service"
  fragment="$(systemctl show --property=FragmentPath --value "$service" 2>/dev/null || true)"
  drop_ins="$(systemctl show --property=DropInPaths --value "$service" 2>/dev/null || true)"
  [[ -z "$drop_ins" ]] || { echo "Refusing to replace $service: it has systemd drop-ins." >&2; exit 1; }
  [[ -z "$fragment" || "$fragment" == "$unit_path" ]] || { echo "Refusing to replace $service: it belongs to another unit path." >&2; exit 1; }
  if [[ -e "$unit_path" || -L "$unit_path" || -n "$fragment" ]]; then
    [[ -f "$unit_path" && ! -L "$unit_path" ]] &&
      grep -Fxq "# Scene2Real managed user=$user" "$unit_path" &&
      grep -Fxq "# Scene2Real managed checkout=$root" "$unit_path" || {
      echo "Refusing to replace $service: its ownership marker or checkout differs." >&2; exit 1;
    }
  fi
done

# Avoid taking over a port used by an unrelated application.
for spec in "$backend_service:$backend_port" "$proxy_service:$proxy_port"; do
  service="${spec%:*}"
  port="${spec##*:}"
  if ! systemctl is-active --quiet "$service"; then
    "$python" -c 'import socket,sys; s=socket.socket(); s.bind(("127.0.0.1",int(sys.argv[1])))' "$port" || { echo "Port $port is already in use." >&2; exit 1; }
  fi
done

umask 077
mkdir -p "$runs_dir"
temp_dir="$(mktemp -d)"
trap 'rm -rf -- "$temp_dir"' EXIT

cat > "$temp_dir/$backend_service" <<EOF
# Scene2Real managed user=$user
# Scene2Real managed checkout=$root
[Unit]
Description=Scene2Real backend
Wants=network-online.target
After=network-online.target
StartLimitIntervalSec=0
[Service]
Type=simple
User=$user
Group=$group
WorkingDirectory="$root"
EnvironmentFile=-"$backend_env"
ExecStart=/usr/bin/env "TEAM_CONFIG=$team_config" "SCENE2REAL_RUNS_DIR=$runs_dir" "PYTHONUNBUFFERED=1" "$python" -m uvicorn scene2real.app:app --host 127.0.0.1 --port $backend_port --workers 1
UMask=0077
Restart=always
RestartSec=3
[Install]
WantedBy=multi-user.target
EOF
cat > "$temp_dir/$proxy_service" <<EOF
# Scene2Real managed user=$user
# Scene2Real managed checkout=$root
[Unit]
Description=Scene2Real authenticated API proxy
Wants=network-online.target
After=network-online.target $backend_service
StartLimitIntervalSec=0
[Service]
Type=simple
User=$user
Group=$group
WorkingDirectory="$root"
EnvironmentFile="$proxy_env"
ExecStart=/usr/bin/env "SCENE2REAL_PROXY_PORT=$proxy_port" "SCENE2REAL_PROXY_UPSTREAM=http://127.0.0.1:$backend_port" "$node" "$root/ops/site_api_proxy.mjs"
UMask=0077
Restart=always
RestartSec=3
[Install]
WantedBy=multi-user.target
EOF
if [[ -n "$tunnel_config" ]]; then
  cat > "$temp_dir/$tunnel_service" <<EOF
# Scene2Real managed user=$user
# Scene2Real managed checkout=$root
[Unit]
Description=Scene2Real named Cloudflare Tunnel
Wants=network-online.target
After=network-online.target $proxy_service
StartLimitIntervalSec=0
[Service]
Type=simple
User=$user
Group=$group
WorkingDirectory="$HOME"
ExecStart="$cloudflared" tunnel --config "$tunnel_config" run
UMask=0077
Restart=always
RestartSec=3
[Install]
WantedBy=multi-user.target
EOF
fi
if command -v systemd-analyze >/dev/null 2>&1; then
  unit_files=()
  for service in "${services[@]}"; do unit_files+=("$temp_dir/$service"); done
  SYSTEMD_UNIT_PATH="$temp_dir:" systemd-analyze verify "${unit_files[@]}" || {
    echo 'Generated systemd unit validation failed; no units were installed.' >&2; exit 1;
  }
fi
for service in "${services[@]}"; do
  sudo -n install -m 0644 "$temp_dir/$service" "/etc/systemd/system/$service"
done
sudo -n systemctl daemon-reload
sudo -n systemctl enable "${services[@]}"
sudo -n systemctl restart "${services[@]}"
for service in "${services[@]}"; do
  systemctl is-active --quiet "$service" || { echo "$service did not start; inspect its journal." >&2; exit 1; }
done
echo "Services started. Backend: 127.0.0.1:$backend_port; proxy: 127.0.0.1:$proxy_port. Check their systemd journals for runtime errors."
echo 'Public routing and end-to-end health must be verified separately.'
