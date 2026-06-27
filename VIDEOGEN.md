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

## Key behavior

Same RunPod cold-start rules as the text model: first request after idle returns `IN_QUEUE` → `IN_PROGRESS` → `COMPLETED` over ~2 min. Retry after 60–90s if you hit 503/502.
