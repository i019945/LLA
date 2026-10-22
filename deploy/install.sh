#!/usr/bin/env bash
# Idempotent installer for the Mac Mini (also the rebuild step on a fresh Mac).
# Needs: git checkout of this repo at ~/LLA, python3, and (for HTTPS) tailscale.
# Never touches ~/lla-data (the production data).
set -euo pipefail
repo="$(cd "$(dirname "$0")/.." && pwd)"
data="$HOME/lla-data"
plist="$HOME/Library/LaunchAgents/com.stevenmeng.lla.plist"

mkdir -p "$data" "$HOME/Library/LaunchAgents"
[ -d "$repo/.venv" ] || python3 -m venv "$repo/.venv"
"$repo/.venv/bin/pip" install -q -r "$repo/requirements.txt"

sed "s#__HOME__#$HOME#g" "$repo/deploy/com.stevenmeng.lla.plist" > "$plist"
launchctl bootout "gui/$(id -u)/com.stevenmeng.lla" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$plist"
echo "service installed; data dir: $data"
echo "next (HTTPS on the tailnet):  tailscale serve --bg --https=443 http://127.0.0.1:8770"
