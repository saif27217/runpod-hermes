# runpod-videogen-hermes

End-to-end 3:4 video generation via RunPod serverless endpoint for Hermes Agent.

## What it does

- Submit video generation jobs to a RunPod endpoint
- Poll until completion
- Download base64-encoded MP4
- Verify video properties

## Endpoint

`cbrzbzlinjhsc0`

## Quick start

```bash
python3 scripts/rp_submit.py --prompt "Your prompt"
python3 scripts/rp_status.py --run-id <RUN_ID>
python3 scripts/rp_save_video.py --run-id <RUN_ID> --output ./video.mp4
```

Or all-in-one:
```bash
bash scripts/rp_complete_video.sh --prompt "Your prompt" --output ./video.mp4
```

## Prerequisites

- Python 3.11+ (stdlib only)
- RunPod API key at `/tmp/rp.key`

## Verified output

- Codec: H.264
- Resolution: 480×720 (portrait, 3:4)
