---
name: runpod
description: "RunPod serverless endpoint → OpenAI-compatible proxy for Hermes Agent. Covers proxy setup, Hermes provider config, and troubleshooting."
version: 1.0.0
author: Sak + Lazer
source: https://github.com/saif27217/runpod-hermes
---

# RunPod Provider for Hermes Agent

A local HTTP proxy that translates OpenAI chat completions requests into RunPod endpoint format and maps responses back.

**Repo**: `saif27217/runpod-hermes` — all scripts live there.

## Setup

```bash
git clone https://github.com/saif27217/runpod-hermes.git ~/runpod-hermes
cd ~/runpod-hermes
```

### Environment variables

```bash
export RUNPOD_ENDPOINT="your-endpoint-id"
export RUNPOD_API_KEY="rpa_..."
```

### Start the proxy

```bash
./runpod-start.sh
# runpod proxy started (pid 12345) on port 8765
```

### Stop

```bash
./runpod-stop.sh
```

## Hermes Provider Config

Add to `~/.hermes/config.yaml`:

```yaml
providers:
  runpod:
    base_url: http://127.0.0.1:8765/v1
    api_key: "placeholder"
    request_timeout_seconds: 300
    stale_timeout_seconds: 300
    models:
      qwen-3.6-35b:
        max_output_tokens: 65536
        context_length: 131072
        timeout_seconds: 300
        stale_timeout_seconds: 300
```

Usage:
```bash
hermes chat -m qwen-3.6-35b --provider runpod -q "hi"
```

## Response Types

| `stream` param | RunPod endpoint | What proxy returns |
|----------------|-----------------|--------------------|
| `false` | `/runsync` | JSON (OpenAI format) |
| `true` | `/runsync` | SSE stream with `reasoning_content` normalised to `content` |

## Troubleshooting

- **"empty stream with no finish_reason"**: Model context too small. Check RunPod response via `curl` to confirm.
- **"502 RunPod upstream error"**: Worker cold start. Wait 1-2 minutes and retry.
- **"IN_QUEUE" / "IN_PROGRESS"**: Worker starting. Proxy returns 503.
- **`$HOME/.hermes/logs/runpod_proxy.log`**: Check proxy logs for detailed error messages.
