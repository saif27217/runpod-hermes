# RunPod Cold Start Behavior

First request after idle triggers worker boot (~1–2 min).

## Stages

| Stage | Proxy response | Timing |
|-------|---------------|--------|
| Cold request | `HTTP 503` with `{"error": {"type": "queue_error"}}` | Worker booting (~40–60s) |
| Retry during boot | `HTTP 502` `"RunPod upstream error"` | Worker still loading |
| After warm | `HTTP 200` | Normal (2–4s) |

## How to handle

1. Send first request — it will likely fail or timeout.
2. Wait 60–90 seconds.
3. Retry same request — it will work.
4. Subsequent requests stay fast while worker is warm.

## Pro tips

- **Warm it up first**: Send `"hi"` before real work. Wait for success.
- **Keep it warm**: Frequent use means no cold starts. RunPod keeps worker alive ~15–30 min.
- **Proxy logs**: Check `$HOME/.hermes/logs/runpod_proxy.log` if unsure.
