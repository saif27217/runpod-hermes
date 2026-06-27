# RunPod Video Generation (3:4 portrait)

End-to-end pipeline for generating 3:4 portrait videos via RunPod serverless endpoint `cbrzbzlinjhsc0`.

## Files

All tooling lives in this folder:

- `videogen/scripts/rp_submit.py` — submit prompt → run ID
- `videogen/scripts/rp_status.py` — poll until `COMPLETED`
- `videogen/scripts/rp_save_video.py` — decode base64 output → MP4
- `videogen/scripts/rp_complete_video.sh` — one-shot submit→poll→save
- `videogen/references/api-quirks.md` — endpoint paths, response shapes
- `videogen/references/cold-start.md` — 503/502 retry strategy

## Verified output

- Codec: H.264
- Resolution: 480×720
- Aspect ratio: 3:4 (portrait)
- Size: ~944 KB per clip

## ⚠️ Cold start / warm-up (required)

Video generation is heavy. The first request after idle triggers worker boot (~1–2 min) and **will** fail with `HTTP 503` / `queue_error`. The correct pattern is:

```bash
# Step 1: Warm up the worker with a tiny request
python3 videogen/scripts/rp_submit.py --prompt "hi"

# Step 2: Wait until status is COMPLETED (or IN_PROGRESS, then poll)
python3 videogen/scripts/rp_status.py --run-id <RUN_ID>

# Step 3: NOW submit your actual video generation job
python3 videogen/scripts/rp_submit.py --prompt "Your real video prompt"
```

Or use the one-shot helper with `--warm-up`:

```bash
bash videogen/scripts/rp_complete_video.sh --prompt "Your real prompt" --output ./video.mp4 --warm-up
```

### Cold-start timeline

| Time | What happens |
|------|--------------|
| 0s | Submit `"hi"` → `IN_QUEUE` |
| ~30s | Worker boots, model loads → `IN_PROGRESS` |
| ~60–120s | Warm-up completes → `COMPLETED` |
| +5s | Submit real prompt → normal speed (2–4s) |

**Do not skip the warm-up step.** Without it, your first real video job will queue behind the boot process and appear to hang or fail.
