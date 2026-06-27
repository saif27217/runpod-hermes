# RunPod Hermes

RunPod serverless endpoint → OpenAI-compatible proxy for [Hermes Agent](https://hermes-agent.nousresearch.com).

Enables Hermes Agent to use RunPod serverless GPU endpoints as a custom model provider.

## Architecture

```
Hermes Agent  →  runpod_proxy.py  →  RunPod API (/runsync)
(OpenAI SDK)     (127.0.0.1:8765)    (serverless GPU endpoint)
```

The proxy translates OpenAI chat completions requests into RunPod's endpoint format and maps responses back. Both streaming and non-streaming paths are supported.

## Files

| File | Purpose |
|------|---------|
| `runpod_proxy.py` | HTTP proxy server (stdlib only — no dependencies) |
| `runpod-start.sh` | Start the proxy daemon |
| `runpod-stop.sh`  | Stop the proxy daemon |

## Quick Start

### 1. Set up RunPod

```bash
export RUNPOD_API_KEY="rpa_..."    # Your RunPod API key
export RUNPOD_ENDPOINT="endpoint_id"  # Serverless endpoint ID
export PROXY_PORT=8765              # Optional, default 8765
```

### 2. Start the proxy

```bash
./runpod-start.sh
```

The script reads `RUNPOD_API_KEY` and `RUNPOD_ENDPOINT` as environment variables and writes the PID to `$HOME/.hermes/runpod_proxy.pid`.

### 3. Test with curl

```bash
# Non-streaming
curl -s http://127.0.0.1:8765/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"hi"}],"model":"qwen-3.6-35b","stream":false}'

# Streaming
curl -s -N http://127.0.0.1:8765/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"hi"}],"model":"qwen-3.6-35b","stream":true}'
```

### 4. Add to Hermes config

```yaml
# ~/.hermes/config.yaml
providers:
  runpod:
    base_url: http://127.0.0.1:8765/v1
    api_key: "placeholder"  # Not checked by local proxy
    request_timeout_seconds: 300
    stale_timeout_seconds: 300
    models:
      qwen-3.6-35b:
        max_output_tokens: 65536
        context_length: 131072
        timeout_seconds: 300
        stale_timeout_seconds: 300
```

Then use:
```bash
hermes chat -m qwen-3.6-35b --provider runpod
```

## How It Works

The proxy uses RunPod's `/runsync` endpoint which handles both streaming and non-streaming responses:

- **Non-streaming** (`stream: false`): Returns RunPod's structured JSON response (list of OpenAI-style completion objects).
- **Streaming** (`stream: true`): RunPod returns a JSON object containing a list of SSE event strings. The proxy parses these, normalizes `reasoning_content` to `content` (for models like Qwen that use `reasoning_content`), and streams them back as standard SSE.

### Error handling

- **FAILED status**: Returns HTTP 400 with RunPod's error message (e.g., context size exceeded).
- **IN_QUEUE / IN_PROGRESS**: Returns HTTP 503 (transient — retryable).
- **No output / timeouts**: Returns 502 with upstream error details.

## Requirements

- Python 3.11+ (stdlib only — no pip dependencies)
- RunPod serverless endpoint (configured to accept `input.messages` JSON)

## License

MIT
