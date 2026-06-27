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

## ❄️ Cold Start

RunPod serverless workers sleep after ~15-30 min idle. The **first request** triggers a cold boot taking **1–2 minutes** — expect `HTTP 503` or `502` initially. Just wait 60–90s and retry the same request. Subsequent requests complete in 2–4s.

Full details in the [README](README.md#-cold-start-behavior).

## 🔧 Tool Calling

The proxy converts non-standard text-embedded tool calls into proper OpenAI `tool_calls` format automatically.

| Format | Example |
|--------|---------|
| JSON | `{"name": "get_weather", "arguments": {"city": "Tokyo"}}` |
| Hermes XML | `<tool_call><function=skill_view><parameter=name>skillname</parameter></function></tool_call>` |

Both `<parameter=key>` and `<parameter name="key">` XML styles supported.

**Smart injection**: If messages already contain `<tool_call>` instructions, the proxy skips JSON format injection to avoid conflicts. Otherwise it injects JSON instructions.

| Scenario | What happens |
|----------|--------------|
| Model outputs text with a tool call JSON block | Proxy parses it, strips it from content, and returns `finish_reason: "tool_calls"` with structured `tool_calls` array |
| Model responds normally without tool calls | Returns standard text response with `finish_reason: "stop"` |
| No tools in request | Behavior unchanged |

Multi-tool calls are supported. Each tool call index gets two SSE chunks (name + arguments) matching the OpenAI spec.

## Logs

- **`$HOME/.hermes/logs/runpod_proxy.log`**: Check proxy logs for detailed error messages.
