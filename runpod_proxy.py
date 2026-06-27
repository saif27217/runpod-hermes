"""RunPod -> OpenAI compatible proxy.

Translates standard OpenAI chat completions requests into RunPod
endpoint format and maps responses back.

Key design: RunPod's /runsync with stream=true blocks until full
generation (~30s+), causing Hermes client timeouts. Instead, this proxy
always requests stream=false from RunPod (completes in ~1-2s), then
streams the chunks back to Hermes as SSE.

Supports tool calling via instruction injection + parser (for models
like Qwen that don't natively output OpenAI tool_calls format on llama.cpp).

Env vars:
  RUNPOD_API_KEY  - RunPod API key (required)
  RUNPOD_ENDPOINT - RunPod endpoint ID (required)
  PROXY_PORT      - listen port (default 8765)
"""

import json
import os
import re
import sys
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.request import Request, urlopen
from urllib.error import HTTPError

# ── Model listing ────────────────────────────────────────────────────────────
# Models this endpoint supports. Hermes sometimes queries GET /v1/models.
AVAILABLE_MODELS = [
    {
        "id": "qwen-3.6-35b",
        "object": "model",
        "created": 1710000000,
        "owned_by": "runpod",
    },
]


def extract_tool_calls(content):
    """Parse JSON tool calls out of text content using json.JSONDecoder.

    Uses raw_decode() which handles arbitrarily nested JSON properly,
    unlike the fragile non-greedy regex approach.
    """
    if not content:
        return [], content or ""

    decoder = json.JSONDecoder()
    tool_calls = []
    clean_content = ""
    last_idx = 0

    # Find all potential tool call starts: {"name": ...
    pattern = r'\{\s*"name"\s*:'
    for match in re.finditer(pattern, content):
        start = match.start()
        try:
            obj, end = decoder.raw_decode(content, start)
            if not isinstance(obj, dict):
                continue
            name = obj.get("name")
            args_val = obj.get("arguments")
            if not isinstance(name, str) or not name:
                continue
            # Serialise arguments (must be a JSON string for OpenAI format)
            if isinstance(args_val, (dict, list)):
                args_serialized = json.dumps(args_val)
            elif isinstance(args_val, str):
                args_serialized = args_val
            else:
                args_serialized = str(args_val) if args_val is not None else "{}"

            clean_content += content[last_idx:start]
            last_idx = end

            tool_calls.append({
                "id": f"call_{name}_{len(tool_calls)}",
                "type": "function",
                "function": {
                    "name": name,
                    "arguments": args_serialized,
                },
            })
        except (json.JSONDecodeError, Exception):
            continue

    clean_content += content[last_idx:]
    return tool_calls, clean_content.strip()


def inject_tool_instructions(messages, tools):
    """Format tool schemas and inject instructions into the system message.

    This tells the model how to express tool calls as JSON text blocks,
    which the proxy then parses and converts to native OpenAI tool_calls format.
    """
    tools_desc = []
    for tool in tools:
        if tool.get("type") == "function":
            fn = tool.get("function", {})
            tools_desc.append({
                "name": fn.get("name"),
                "description": fn.get("description", ""),
                "parameters": fn.get("parameters", {}),
            })

    instructions = (
        "\n\n[TOOL USE INSTRUCTION]\n"
        "You have access to the following tools that you can call:\n"
        f"{json.dumps(tools_desc, indent=2)}\n\n"
        "When you decide to use a tool, you MUST output it as a raw JSON object "
        "on its own line(s) with no surrounding text on that line, in this exact format:\n"
        '{"name": "tool_name", "arguments": { ... }}\n'
        "You can call MULTIPLE tools — just output each one on its own line.\n"
        "Examples:\n"
        '{"name": "get_weather", "arguments": {"city": "Tokyo"}}\n'
        '{"name": "search_web", "arguments": {"query": "Tokyo weather"}}\n'
        "You may include text BEFORE the tool call JSON objects, but nothing after.\n"
        "If you do not need to call a tool, just answer normally without outputting JSON."
    )

    new_messages = [dict(m) for m in messages]

    # Find or create a system message
    system_msg = None
    for msg in new_messages:
        if msg.get("role") == "system":
            system_msg = msg
            break

    if system_msg:
        system_msg["content"] = system_msg.get("content", "") + instructions
    else:
        new_messages.insert(0, {
            "role": "system",
            "content": "You are a helpful assistant with access to tools. Use them when appropriate." + instructions,
        })

    return new_messages


class Handler(BaseHTTPRequestHandler):
    model_id = "qwen-3.6-35b"

    # ── GET: model listing ─────────────────────────────────────────────
    def do_GET(self):
        if self.path in ("/v1/models", "/models", "/api/v1/models"):
            body = json.dumps({
                "object": "list",
                "data": AVAILABLE_MODELS,
            }).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_error(404, f"Not Found: {self.path}")

    # ── POST: chat completions ─────────────────────────────────────────
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
        tools = openai_req.get("tools", [])
        has_tools = bool(tools)

        if has_tools:
            messages = inject_tool_instructions(messages, tools)

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

        # Extract message content (check both content and reasoning_content)
        choice = openai_resp.get("choices", [{}])[0]
        message = choice.get("message", {})
        content = message.get("content", "") or ""
        reasoning = message.get("reasoning_content", "") or ""
        model_id = openai_resp.get("model", openai_req.get("model", "runpod-model"))
        resp_id = openai_resp.get("id", f"chatcmpl-runpod-{int(time.time())}")
        created = openai_resp.get("created", int(time.time()))

        # Some Qwen/DeepSeek models put everything in reasoning_content
        all_text = content or reasoning

        # Parse tool calls from text if tools are active
        tool_calls = []
        if has_tools and all_text:
            tool_calls, clean_content = extract_tool_calls(all_text)
            if tool_calls:
                content = clean_content
                message["content"] = clean_content
                message["tool_calls"] = tool_calls
                choice["finish_reason"] = "tool_calls"

                # Also null out reasoning_content when we found tool calls
                if reasoning:
                    message.pop("reasoning_content", None)

        # ── Streaming response ──────────────────────────────────────────────
        if stream:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.end_headers()

            # 1. Role chunk
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
            self._sse_send(role_chunk)

            # 2. Content chunk(s) — if there's clean text before tool calls
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
                self._sse_send(content_chunk)

            # 3. Tool call chunks — one per tool call index, per OpenAI spec
            if tool_calls:
                for idx, tc in enumerate(tool_calls):
                    # 3a. Name / id / type chunk for this tool call index
                    name_chunk = {
                        "id": resp_id,
                        "object": "chat.completion.chunk",
                        "created": created,
                        "model": model_id,
                        "choices": [{
                            "index": 0,
                            "delta": {
                                "tool_calls": [{
                                    "index": idx,
                                    "id": tc["id"],
                                    "type": "function",
                                    "function": {
                                        "name": tc["function"]["name"],
                                        "arguments": "",
                                    },
                                }],
                            },
                            "finish_reason": None,
                        }],
                    }
                    self._sse_send(name_chunk)

                    # 3b. Arguments chunk for this tool call index
                    args_chunk = {
                        "id": resp_id,
                        "object": "chat.completion.chunk",
                        "created": created,
                        "model": model_id,
                        "choices": [{
                            "index": 0,
                            "delta": {
                                "tool_calls": [{
                                    "index": idx,
                                    "function": {
                                        "arguments": tc["function"]["arguments"],
                                    },
                                }],
                            },
                            "finish_reason": None,
                        }],
                    }
                    self._sse_send(args_chunk)

            # 4. Finish chunk
            finish_chunk = {
                "id": resp_id,
                "object": "chat.completion.chunk",
                "created": created,
                "model": model_id,
                "choices": [{
                    "index": 0,
                    "delta": {},
                    "finish_reason": "tool_calls" if tool_calls else "stop",
                }],
            }
            self._sse_send(finish_chunk)

            self.wfile.write(b"data: [DONE]\n\n")
            self.wfile.flush()
            return

        # ── Non-streaming response ──────────────────────────────────────────
        response_body = json.dumps(openai_resp).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(response_body)))
        self.end_headers()
        self.wfile.write(response_body)

    def _sse_send(self, chunk):
        """Write a single SSE data frame."""
        self.wfile.write(("data: " + json.dumps(chunk) + "\n\n").encode())
        self.wfile.flush()

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
