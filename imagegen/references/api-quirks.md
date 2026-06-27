# RunPod SD API Quirks

## Endpoint paths

- `/run` — async submission, returns `{"id": ..., "status": "IN_QUEUE"}`
- `/runSync` — synchronous, blocks until done
- `/status/<run_id>` — poll for completion

## Request format

```json
{
  "input": {
    "prompt": "text prompt",
    "negative_prompt": "what to avoid",
    "width": 512,
    "height": 512,
    "num_inference_steps": 20,
    "guidance_scale": 7.5,
    "seed": 42,
    "batch_size": 1
  }
}
```

## Response format

Success (`COMPLETED`):
```json
{
  "output": {
    "images": ["<base64>"],
    "info": "...",
    "parameters": "..."
  }
}
```

## Auth

`Authorization: Bearer *** API key>` header. API key at `/tmp/rp.key`.

## Cold start

First request may take 1–2 min. Subsequent requests ~15–30s.
