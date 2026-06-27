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

## ❄️ Cold Start Behavior

This is the #1 source of confusion when using RunPod serverless endpoints. **Read this carefully — it will save you frustration.**

### What happens

When a RunPod serverless endpoint has been idle for a while (typically 15–30 min), the GPU worker goes to sleep. The **first request** after idle triggers a cold boot:

```
Request → IN_QUEUE (worker waking up) → IN_PROGRESS (loading model) → COMPLETED
```

This takes **1–2 minutes** on a cold worker. Afterwards, subsequent requests complete in **2–4 seconds** while the worker stays warm.

### What you'll see

| Stage | Proxy response | What's happening |
|-------|---------------|-----------------|
| First request on cold worker | `HTTP 503` with `{"error": {"type": "queue_error"}}` | Worker booting, model loading (~40-60s) |
| Retry during boot | `HTTP 502` `"RunPod upstream error"` | Worker still loading, request timed out |
| After worker is warm | `HTTP 200` with normal response | Model loaded, works normally |

### How to handle it

**Don't panic.** This is normal, not a broken setup.

1. **Send your first request** — it will almost certainly fail or timeout.
2. **Wait 60–90 seconds** (go make tea, check your phone).
3. **Send the same request again** — it will work instantly.
4. From then on, all requests work normally until the worker goes idle again.

If you're using Hermes Agent with a large timeout setting (≥300s as shown in the config example above), the first request may hang for a while before failing. This is the proxy waiting for the worker to wake up.

### Pro tips

- **Warm it up first**: Send a short test request (`"hi"` or `"ping"`) before your real work. Wait for success, then proceed.
- **Keep it warm**: RunPod keeps the worker alive ~15-30 min after the last request. Frequent use means no cold starts.
- **The proxy logs** at `$HOME/.hermes/logs/runpod_proxy.log` show exactly what stage you're in — check there if you're unsure.
- **For Hermes config**: The `timeout_seconds: 300` and `stale_timeout_seconds: 300` settings give the worker enough time to cold-boot without the client giving up early.

## 🔧 Tool Calling

The proxy converts non-standard text-embedded tool calls into proper OpenAI `tool_calls` format automatically.

| Scenario | What happens |
|----------|--------------|
| Model outputs text with a tool call JSON block | Proxy parses it, strips it from content, and returns `finish_reason: "tool_calls"` with structured `tool_calls` array |
| Model responds normally without tool calls | Returns standard text response with `finish_reason: "stop"` |
| No tools in request | Behavior unchanged |

### Multi-tool calls

The proxy supports multiple tool calls in a single response. The instruction injection tells the model it can output multiple JSON objects, and the parser handles all of them.

**Streaming format**: Each tool call index gets two SSE chunks:
1. Name/ID chunk (`{"name": "tool_name", "arguments": ""}`)
2. Arguments chunk (`{"arguments": "..."}`)

This matches the OpenAI streaming spec exactly, so Hermes/openai client SDK accumulates tool calls correctly by index.

### Known limitations & fixes

| Issue | Fix |
|-------|-----|
| Model only outputs one tool call | Instruction changed from "a single JSON object" to "one or more JSON objects" |
| Streaming breaks with multiple tool calls | Tool call indices now streamed separately per OpenAI spec |
| Tool calls in `reasoning_content` are missed | Proxy now checks both `content` and `reasoning_content` |
| `GET /v1/models` returns 501 | Proxy now serves the model list at `/v1/models`, `/models`, `/api/v1/models` |
| Fragile regex breaks on nested JSON in arguments | Now uses `json.JSONDecoder.raw_decode()` for proper brace matching |

### How it works

1. The proxy intercepts the `tools` parameter from the OpenAI request
2. Injects a system instruction telling the model to output tool calls as raw JSON objects at the end of its response
3. Sends the modified request to RunPod (always non-streaming, to avoid timeouts)
4. Parses the response using `json.JSONDecoder.raw_decode()` to find all tool call JSON objects
5. Strips the JSON from `content` and formats as OpenAI `tool_calls`
6. For streaming requests: sends correct SSE chunks with per-index tool call deltas + finish_reason

## Requirements

- Python 3.11+ (stdlib only — no pip dependencies)
- RunPod serverless endpoint (configured to accept `input.messages` JSON)

## License

MIT
