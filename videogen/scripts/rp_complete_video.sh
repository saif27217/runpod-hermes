#!/usr/bin/env bash
# All-in-one: submit → poll → save video
set -euo pipefail

PROMPT="${1:-Your prompt}"
OUTPUT="${2:-/tmp/runpod_video.mp4}"
ENDPOINT="${RUNPOD_ENDPOINT:-cbrzbzlinjhsc0}"
KEY_FILE="${RUNPOD_KEY_FILE:-/tmp/rp.key}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "[1/3] Submitting job..."
RUN_ID=$(python3 "${SCRIPT_DIR}/rp_submit.py" \
  --prompt "$PROMPT" \
  --endpoint "$ENDPOINT" \
  --key-file "$KEY_FILE")

if [ -z "$RUN_ID" ]; then
  echo "Failed to get run ID" >&2
  exit 1
fi

echo "Run ID: $RUN_ID"
echo "[2/3] Polling for completion..."
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

echo "[3/3] Saving video..."
python3 "${SCRIPT_DIR}/rp_save_video.py" \
  --run-id "$RUN_ID" \
  --endpoint "$ENDPOINT" \
  --key-file "$KEY_FILE" \
  --output "$OUTPUT"

echo "Done: $OUTPUT"
