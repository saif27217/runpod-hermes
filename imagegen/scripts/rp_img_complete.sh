#!/usr/bin/env bash
# All-in-one: submit → poll → save image
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

PROMPT=""
NEGATIVE_PROMPT="blurry, bad quality"
WIDTH=512
HEIGHT=512
STEPS=20
CFG=7.5
SEED=-1
BATCH=1
OUTPUT="/tmp/runpod_image.png"
ENDPOINT="${RUNPOD_ENDPOINT:-187vrz5cvrrxl6}"
KEY_FILE="${RUNPOD_KEY_FILE:-/tmp/rp.key}"

# Parse flags
while [ $# -gt 0 ]; do
  case "$1" in
    --prompt) PROMPT="$2"; shift 2 ;;
    --negative-prompt) NEGATIVE_PROMPT="$2"; shift 2 ;;
    --width) WIDTH="$2"; shift 2 ;;
    --height) HEIGHT="$2"; shift 2 ;;
    --steps) STEPS="$2"; shift 2 ;;
    --cfg) CFG="$2"; shift 2 ;;
    --seed) SEED="$2"; shift 2 ;;
    --batch) BATCH="$2"; shift 2 ;;
    --output) OUTPUT="$2"; shift 2 ;;
    --endpoint) ENDPOINT="$2"; shift 2 ;;
    --key-file) KEY_FILE="$2"; shift 2 ;;
    *) shift ;;
  esac
done

if [ -z "$PROMPT" ]; then
  echo "Error: --prompt is required" >&2
  exit 1
fi

echo "[1/3] Submitting image job..."
RUN_ID=$(python3 "${SCRIPT_DIR}/rp_img_submit.py" \
  --prompt "$PROMPT" \
  --negative-prompt "$NEGATIVE_PROMPT" \
  --width "$WIDTH" \
  --height "$HEIGHT" \
  --steps "$STEPS" \
  --cfg "$CFG" \
  --seed "$SEED" \
  --batch "$BATCH" \
  --endpoint "$ENDPOINT" \
  --key-file "$KEY_FILE")

if [ -z "$RUN_ID" ]; then
  echo "Failed to get run ID" >&2
  exit 1
fi

echo "Run ID: $RUN_ID"
echo "[2/3] Polling for completion..."
while true; do
  STATUS=$(python3 "${SCRIPT_DIR}/rp_img_status.py" \
    --run-id "$RUN_ID" \
    --endpoint "$ENDPOINT" \
    --key-file "$KEY_FILE" 2>/dev/null | head -1 | cut -d' ' -f2)
  echo "$(date '+%H:%M:%S') $STATUS"
  if [ "$STATUS" = "COMPLETED" ] || [ "$STATUS" = "FAILED" ] || [ "$STATUS" = "CANCELLED" ]; then
    break
  fi
  sleep 15
done

if [ "$STATUS" != "COMPLETED" ]; then
  echo "Job ended with status: $STATUS" >&2
  exit 1
fi

echo "[3/3] Saving image..."
python3 "${SCRIPT_DIR}/rp_img_save.py" \
  --run-id "$RUN_ID" \
  --endpoint "$ENDPOINT" \
  --key-file "$KEY_FILE" \
  --output "$OUTPUT"

echo "Done: $OUTPUT"
