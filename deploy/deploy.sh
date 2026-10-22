#!/usr/bin/env bash
# Run ON the Mac Mini: pull the latest code from GitHub and restart the service.
# Code only. Data in ~/lla-data is never touched.
set -euo pipefail
cd "$(dirname "$0")/.."
git fetch -q origin
git merge --ff-only origin/main
.venv/bin/pip install -q -r requirements.txt
launchctl kickstart -k "gui/$(id -u)/com.stevenmeng.lla"
sleep 2
curl -fsS http://127.0.0.1:8770/healthz && echo " <- healthz ok, now at $(git rev-parse --short HEAD)"
