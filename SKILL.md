---
name: runpod-videogen-hermes
description: "End-to-end 3:4 video generation via RunPod serverless endpoint. Covers job submission, polling, base64 video retrieval, and verification."
version: 1.0.0
author: Sak + Lazer
source: https://github.com/saif27217/runpod-videogen-hermes
---

# RunPod Video Generation for Hermes

Generate 3:4 portrait videos via a RunPod serverless endpoint (`cbrzbzlinjhsc0`), poll until completion, download the base64-encoded MP4, and verify the file.

## Files in this repo

| File | Purpose |
|------|---------|
| `scripts/rp_submit.py` | Submit a video generation job to RunPod |
| `scripts/rp_status.py` | Check job status + show output metadata |
| `scripts/rp_save_video.py` | Download base64 video from completed run and save as MP4 |
| `scripts/rp_complete_video.sh` | One-shot helper: submit → poll → save |
| `references/cold-start.md` | RunPod cold-start behavior and retry strategy |
| `references/api-quirks.md` | RunPod API quirks and response formats |

## Prerequisites

- Python 3.11+ (stdlib only — no pip dependencies)
- RunPod API key stored at `/tmp/rp.key` (chmod 600)
- RunPod endpoint ID: `cbrzbzlinjhsc0`

## Quick start

### 1. Submit a job
```bash
python3 scripts/rp_submit.py --prompt "Your prompt here"
```

### 2. Check status
```bash
python3 scripts/rp_status.py --run-id <RUN_ID>
```

### 3. Download the video
```bash
python3 scripts/rp_save_video.py --run-id <RUN_ID> --output /path/to/video.mp4
```

### 4. Or run all-in-one
```bash
bash scripts/rp_complete_video.sh --prompt "Your prompt here" --output ./video.mp4
```

## How it works

1. **Submit** → POST to `/v2/<endpoint>/run` with `{"input": {"prompt": "..."}}`
2. **Poll** → GET `/v2/<endpoint>/status/<run_id>` every 30–60s
3. **Download** → `output` field is a huge base64 string containing the MP4
4. **Verify** → `ffprobe` shows `h264`, `480x720` (portrait)

## Cold start

First request after idle triggers worker boot (~1–2 min). You'll see `IN_QUEUE` → `IN_PROGRESS` → `COMPLETED`. Retry same request after 60–90s if you hit `HTTP 503/502`.

## Verification

```bash
ffprobe -v error -select_streams v:0 -show_entries stream=codec_name,width,height \
  -of default=noprint_wrappers=1 /path/to/video.mp4
```

Expected:
- `codec_name=h264`
- `width=480`
- `height=720`
