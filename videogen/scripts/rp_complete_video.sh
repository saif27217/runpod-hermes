#!/usr/bin/env bash
# All-in-one: warm-up → submit → poll → save video
set -euo pipefail

PROMPT="${1:-Your prompt}"
OUTPUT="${2:-/tmp/runpod_video.mp4}"
ENDPOINT="${RUNPOD_ENDPOINT:-cbrzbzlinjhsc0}"
KEY_FILE="${RUNPOD_KEY_FILE:-/tmp/rp.key}"
WARM_UP="${WARM_UP:-1}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Parse flags
while [ $# -gt 0 ]; do
  case "$1" in
    --prompt) PROMPT="$2"; shift 2 ;;
    --output) OUTPUT="$2"; shift 2 ;;
    --warm-up) WARM_UP="1"; shift ;;
    --no-warm-up) WARM_UP="0"; shift ;;
    *) shift ;;
  esac
done

# Step 0: Warm up the worker if enabled
if [ "$WARM_UP" = "1" ]; then
  echo "[0/4] Warming up worker (sending 'hi')..."
  WARM_ID=$(python3 "${SCRIPT_DIR}/rp_submit.py" \
    --prompt "hi" \
    --endpoint "$ENDPOINT" \
    --key-file "$KEY_FILE")
  if [ -n "$WARM_ID" ]; then
    echo "Warm-up run ID: $WARM_ID"
    while true; do
      STATUS=$(python3 "${SCRIPT_DIR}/rp_status.py" \
        --run-id "$WARM_ID" \
        --endpoint "$ENDPOINT" \
        --key-file "$KEY_FILE" 2>/dev/null | head -1 | cut -d' ' -f2)
      echo "$(date '+%H:%M:%S') warm-up: $STATUS"
      if [ "$STATUS" = "COMPLETED" ] || [ "$STATUS" = "FAILED" ] || [ "$STATUS" = "CANCELLED" ]; then
        break
      fi
      sleep 30
    done
    echo "Warm-up done."
  fi
fi

# Step 1: Submit actual job
echo "[1/4] Submitting job..."
RUN_ID=$(python3 "${SCRIPT_DIR}/rp_submit.py" \
  --prompt "$PROMPT" \
  --endpoint "$ENDPOINT" \
  --key-file "$KEY_FILE")

if [ -z "$RUN_ID" ]; then
  echo "Failed to get run ID" >&2
  exit 1
fi

echo "Run ID: $RUN_ID"
echo "[2/4] Polling for completion..."
while true; do
  STATUS=$(python3 "${SCRIPT_DIR}/rp_status.py" \
    --run-id "$RUN_ID" \
    --endpoint "$ENDPOINT" \
    --key-file "$KEY_FILE" 2>/dev/null | head -1 | cut -d' ' -f2)
  echo "$(date '+%H:%M:%S') $STATUS"
  if [ "$STATUS" = "COMPLETED" ] || [ "$STATUS" = "FAILED" ] || [ "$STATUS" = "CANCELLED" ]; then
    break
  fi
  sleep 30
done

if [ "$STATUS" != "COMPLETED" ]; then
  echo "Job ended with status: $STATUS" >&2
  exit 1
fi

echo "[3/4] Saving video..."
python3 "${SCRIPT_DIR}/rp_save_video.py" \
  --run-id "$RUN_ID" \
  --endpoint "$ENDPOINT" \
  --key-file "$KEY_FILE" \
  --output "$OUTPUT"

echo "[4/4] Done: $OUTPUT"
