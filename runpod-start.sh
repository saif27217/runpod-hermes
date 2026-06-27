#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROXY="$SCRIPT_DIR/runpod_proxy.py"
PIDFILE="$HOME/.hermes/runpod_proxy.pid"
LOGFILE="$HOME/.hermes/logs/runpod_proxy.log"
PORT="${PROXY_PORT:-8765}"

mkdir -p "$(dirname "$PIDFILE")" "$(dirname "$LOGFILE")"

if [[ -f "$PIDFILE" ]] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
    echo "runpod proxy already running (pid $(cat "$PIDFILE")) on port $PORT"
    exit 0
fi

# Expect these env vars to be set before calling this script:
#   RUNPOD_ENDPOINT, RUNPOD_API_KEY
: "${RUNPOD_ENDPOINT:?Set RUNPOD_ENDPOINT}"
: "${RUNPOD_API_KEY:?Set RUNPOD_API_KEY}"

export PROXY_PORT="$PORT"
nohup python3 "$PROXY" >> "$LOGFILE" 2>&1 &
echo $! > "$PIDFILE"
echo "runpod proxy started (pid $!) on port $PORT"
