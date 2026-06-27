#!/usr/bin/env bash
set -euo pipefail

PIDFILE="$HOME/.hermes/runpod_proxy.pid"

if [[ -f "$PIDFILE" ]] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
    kill "$(cat "$PIDFILE")"
    rm -f "$PIDFILE"
    echo "runpod proxy stopped"
else
    echo "runpod proxy not running"
    exit 1
fi
