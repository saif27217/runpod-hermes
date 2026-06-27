# RunPod API Quirks

## Endpoint paths

- `/run` — async submission, returns `{"id": ..., "status": "IN_QUEUE"}`
- `/runSync` — synchronous, blocks until done (use for short jobs)
- `/status/<run_id>` — poll for completion

## Response format

Success:
```json
{
  "id": "...",
  "status": "COMPLETED",
  "output": "<base64-encoded video or text>",
  "workerId": "..."
}
```

Queue states:
- `IN_QUEUE` — worker waking up
- `IN_PROGRESS` — processing
- `COMPLETED` — done
- `FAILED` — error
- `CANCELLED` — cancelled

## Output formats

For video endpoints: `output` is a JSON string like:
```json
{"video": "AAAAIGZ0eXBpc29t..."}
```

Where the `video` value is a huge base64 string of the MP4 file.

## Auth

Use `Authorization: Bearer <RunPod API key>` header. API key is stored at `/tmp/rp.key` in this setup.

## Cold start

First request always cold-boots (1–2 min). Handle 503/502 and retry.
