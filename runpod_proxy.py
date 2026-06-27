"""RunPod -> OpenAI compatible proxy.

Translates standard OpenAI chat completions requests into RunPod
endpoint format and maps responses back.

Key design: RunPod's /runsync with stream=true blocks until full
generation (~30s+), causing Hermes client timeouts. Instead, this proxy
always requests stream=false from RunPod (completes in ~1-2s), then
streams the chunks back to Hermes as SSE.

Env vars:
  RUNPOD_API_KEY  - RunPod API key (required)
  RUNPOD_ENDPOINT - RunPod endpoint ID (required)
  PROXY_PORT      - listen port (default 8765)
"""

import json
import os
import sys
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.request import Request, urlopen
from urllib.error import HTTPError


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path != "/v1/chat/completions":
            self.send_error(404, "Not Found")
            return

        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)

        try:
            openai_req = json.loads(body)
        except json.JSONDecodeError as e:
            self.send_error(400, f"Invalid JSON: {e}")
            return

        messages = openai_req.get("messages", [])
        if not messages:
            self.send_error(400, "Missing messages")
            return

        stream = openai_req.get("stream", False)

        endpoint = os.environ.get("RUNPOD_ENDPOINT")
        api_key = os.environ.get("RUNPOD_API_KEY")
        if not endpoint or not api_key:
            self.send_error(500, "RUNPOD_ENDPOINT and RUNPOD_API_KEY must be set")
            return

        # Always request non-streaming from RunPod to avoid 30s+ blocking
        runpod_url = f"https://api.runpod.ai/v2/{endpoint}/runsync"
        runpod_payload = {
            "input": {
                "messages": messages,
                "stream": False,
            }
        }

        if "model" in openai_req:
            runpod_payload["input"]["model"] = openai_req["model"]

        req = Request(
            runpod_url,
            data=json.dumps(runpod_payload).encode(),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
            method="POST",
        )

        try:
            with urlopen(req, timeout=300) as resp:
                runpod_resp = json.loads(resp.read().decode())
        except HTTPError as e:
            self.send_response(e.code)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(e.read())
            return
        except Exception as e:
            self.send_error(502, f"RunPod upstream error: {e}")
            return

        output = runpod_resp.get("output")

        # Handle RunPod errors and queue states
        status = runpod_resp.get("status", "?")
        if status == "IN_QUEUE":
            self.send_response(503)
            self.send_header("Retry-After", "30")
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({
                "error": {"message": f"RunPod queue: {runpod_resp.get('id', '')}", "type": "queue_error"}
            }).encode())
            return

        if status == "FAILED":
            error_msg = runpod_resp.get("error", "Unknown RunPod error")
            self.send_error(400, f"RunPod error: {error_msg}")
            return

        if isinstance(output, list) and len(output) > 0:
            openai_resp = output[0]
        elif isinstance(output, dict):
            openai_resp = output
        else:
            openai_resp = {
                "id": runpod_resp.get("id", ""),
                "object": "chat.completion",
                "created": runpod_resp.get("created", 0),
                "model": openai_req.get("model", "runpod-model"),
                "choices": [{
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": str(runpod_resp),
                    },
                    "finish_reason": "stop",
                }],
            }

        # Extract message and content
        choice = openai_resp.get("choices", [{}])[0]
        message = choice.get("message", {})
        content = message.get("content", "")
        reasoning = message.get("reasoning_content", "")
        model_id = openai_resp.get("model", openai_req.get("model", "runpod-model"))
        resp_id = openai_resp.get("id", f"chatcmpl-runpod-{int(time.time())}")
        created = openai_resp.get("created", int(time.time()))

        if stream:
            # Stream as SSE: first role chunk, then content chunks, then finish
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.end_headers()

            # Role chunk
            role_chunk = {
                "id": resp_id,
                "object": "chat.completion.chunk",
                "created": created,
                "model": model_id,
                "choices": [{
                    "index": 0,
                    "delta": {"role": "assistant"},
                    "finish_reason": None,
                }],
            }
            self.wfile.write(("data: " + json.dumps(role_chunk) + "\n\n").encode())
            self.wfile.flush()

            # Content chunk(s) — send full content in one chunk
            if content:
                content_chunk = {
                    "id": resp_id,
                    "object": "chat.completion.chunk",
                    "created": created,
                    "model": model_id,
                    "choices": [{
                        "index": 0,
                        "delta": {"content": content},
                        "finish_reason": None,
                    }],
                }
                self.wfile.write(("data: " + json.dumps(content_chunk) + "\n\n").encode())
                self.wfile.flush()

            # Finish chunk
            finish_chunk = {
                "id": resp_id,
                "object": "chat.completion.chunk",
                "created": created,
                "model": model_id,
                "choices": [{
                    "index": 0,
                    "delta": {},
                    "finish_reason": "stop",
                }],
            }
            self.wfile.write(("data: " + json.dumps(finish_chunk) + "\n\n").encode())
            self.wfile.flush()

            self.wfile.write(b"data: [DONE]\n\n")
            self.wfile.flush()
            return

        # Non-streaming: return OpenAI chat completion format
        response_body = json.dumps(openai_resp).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(response_body)))
        self.end_headers()
        self.wfile.write(response_body)

    def log_message(self, format, *args):
        sys.stderr.write("%s - - [%s] %s\n" % (
            self.client_address[0],
            self.log_date_time_string(),
            format % args,
        ))


def main():
    port = int(os.environ.get("PROXY_PORT", "8765"))
    endpoint = os.environ.get("RUNPOD_ENDPOINT", "")
    api_key = os.environ.get("RUNPOD_API_KEY", "")

    if not endpoint or not api_key:
        print("ERROR: RUNPOD_ENDPOINT and RUNPOD_API_KEY must be set", file=sys.stderr)
        sys.exit(1)

    server = HTTPServer(("127.0.0.1", port), Handler)
    print(f"PROXY STARTED {__file__} on http://127.0.0.1:{port}/v1/chat/completions")
    print(f"ENDPOINT {os.environ.get('RUNPOD_ENDPOINT','')}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.server_close()


if __name__ == "__main__":
    main()
