#!/usr/bin/env python3
"""
Model Router Proxy for Claude Code
==================================
Receives Anthropic-format requests → judges complexity via Ollama →
routes to DashScope Anthropic-compatible endpoint (transparent passthrough).

Usage:
    python3 model_router.py
    python3 model_router.py --port 9000
"""

import json
import random
import re
import sys
import time

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import Response, StreamingResponse

# ─── Global HTTP Client with connection pooling ────────────────────────

_global_client = None


def get_http_client():
    """Get global httpx.AsyncClient with connection pooling."""
    global _global_client
    if _global_client is None:
        _global_client = httpx.AsyncClient(
            timeout=300.0,
            limits=httpx.Limits(
                max_connections=100,
                max_keepalive_connections=20,
                keepalive_expiry=60.0,
            ),
        )
    return _global_client


async def request_with_retry(client, method, url, headers, data, retries=3):
    """Make HTTP request with exponential backoff retry for transient errors."""
    last_exception = None

    for attempt in range(retries):
        try:
            if method == "post":
                resp = await client.post(url, content=data, headers=headers)
            else:
                resp = await client.get(url, headers=headers)

            # Retry on 5xx errors
            if resp.status_code >= 500:
                raise httpx.HTTPError(f"Server error: {resp.status_code}")

            return resp

        except (httpx.ConnectError, httpx.TimeoutException) as e:
            last_exception = e
            if attempt < retries - 1:
                wait = 0.5 * (2**attempt) + random.uniform(0, 0.3)
                log(f"[WARN] Retry {attempt+1}/{retries} after {wait:.1f}s: {e}")
                await httpx.sleep(wait)

    raise last_exception

# ─── Configuration ───────────────────────────────────────────────────

HOST = "0.0.0.0"
PORT = 8888
JUDGE_MODEL = "qwen2.5:1.5b"
OLLAMA_PORT = 11434
OLLAMA_TIMEOUT = 8
DASHSCOPE_API_KEY = "your-api-key-here"
# DashScope native Anthropic-compatible endpoint — no format conversion needed
DASHSCOPE_BASE = "https://dashscope.aliyuncs.com/apps/anthropic"
CHEAP_MODEL = "qwen3.5-flash"
EXPENSIVE_MODEL = "qwen3.6-plus"

# ─── App ─────────────────────────────────────────────────────────────

app = FastAPI(title="Model Router")


def log(msg: str):
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}", flush=True)


async def extract_text_content(message: dict) -> str:
    """Extract readable text content from a message dict."""
    content = message.get("content", "")

    if isinstance(content, str):
        return content.strip()

    if isinstance(content, list):
        texts = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text") or item.get("content") or ""
                if isinstance(text, str):
                    texts.append(text.strip())
        return " ".join(texts)

    return str(content).strip()


def is_valid_user_message(text: str) -> bool:
    """Check if this looks like a valid natural language user message."""
    text_lower = text.lower().strip()

    # Special handling for "test" - it's a valid (low complexity) input
    if text_lower in ("test", "testing"):
        return True

    # Filter out tool-related content and UI artifacts
    if any(pattern in text_lower for pattern in [
        '<tool_use_id', '<tool-result', 'tool_result',
        '<tool-use', 'tool_use_', 'toolresult',
        'command running in background', 'output is being written to',
        '<system-reminder', 'sessionstart hook',
        'task # created successfully',
        'exit code', 'parse error', 'syntaxerror',
        'blocked', 'not ready', '/clear', '<tool_use_error>',
        '<tool-use-error>', 'sleep followed by',
        '<retrieval_status>', 'background agent completed'
    ]):
        return False

    # Must contain at least some letters, digits, or Chinese/Japanese characters
    has_letters = any(c.isalpha() for c in text)
    has_digits = any(c.isdigit() for c in text)
    has_chinese = any('\u4e00' <= c <= '\u9fff' for c in text)
    has_japanese = any('\u3040' <= c <= '\u30ff' for c in text)

    if not (has_letters or has_digits or has_chinese or has_japanese):
        return False

    return True


# ─── Complexity Judge ────────────────────────────────────────────────

async def judge_complexity(user_messages: list, system_prompt: str = "") -> int:
    """Ask Ollama to classify task complexity. Returns integer 1-10."""
    # Only use the LAST valid user message - exclude system_prompt and prior context
    # to avoid polluting the judgment with irrelevant context
    if not user_messages:
        context = "(no valid messages)"
    else:
        text = await extract_text_content(user_messages[-1])
        context = text if text else "(no valid messages)"

    if len(context) > 2000:
        context = context[:2000] + "..."

    # Use /api/generate for better instruction-following with small models
    prompt = (
        "You are a top-tier LLM Router Gateway. Evaluate the semantic complexity and logical reasoning depth of the user's input, and output a complexity score from 1 to 10.\n\n"
        "=== Lightweight Interval: Levels 1-5 (Execution-layer tasks: no deep reasoning, pattern matching) ===\n"
        "Level 1: Greetings, thanks, meaningless tests (e.g., 'test', 'hello').\n"
        "Level 2: Simple word translation, spell check, case conversion.\n"
        "Level 3: The Basics, QA (e.g., 'how big is Earth'), extracting explicit info from short text (names, dates).\n"
        "Level 4: Simple summarization, writing a routine email, basic formatting (paragraph to list).\n"
        "Level 5: Text generation with a few constraints (e.g., 'write a 300-word essay on spring'), very basic code (e.g., 'write a bubble sort in Python').\n"
        "--- >> Routing Threshold: Above this line requires strong reasoning ability << ---\n\n"
        "=== Heavyweight Interval: Levels 6-10 (Thinking-layer tasks: multi-step reasoning, logical deduction, deep expertise) ===\n"
        "Level 6: Creative tasks with 3+ constraints, medium-difficulty code generation, logic puzzle analysis, deep analysis requiring specific context.\n"
        "Level 7: Complex code debugging, API integration design, database schema planning, error log troubleshooting.\n"
        "Level 8: Deep analysis in law/medicine/finance/academia, chart-based logical reasoning with heavy data, academic-level writing or polishing.\n"
        "Level 9: Multi-step planning, Monumental Task (e.g., 'plan a complete New Year event with budget, schedule, and promotional copy').\n"
        "Level 10: Extremely complex math derivations, innovative algorithm design beyond conventional thinking, massive intertwined novel worldbuilding.\n\n"
        "Evaluate considering: (1) Multi-step reasoning needed? (2) Many constraints? (3) Requires professional expertise? (4) High cost of error?\n"
        "Respond with ONLY a single integer from 1 to 10, nothing else.\n\n"
        f"User input: {context}\nComplexity score:"
    )

    payload = {
        "model": JUDGE_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0, "num_predict": 3},
    }

    try:
        client = get_http_client()
        resp = await client.post(f"http://localhost:{OLLAMA_PORT}/api/generate", json=payload)
        data = resp.json()
        content = data.get("response", "").strip()

        if not content:
            log("[WARN] Judge returned empty response, defaulting to 5")
            return 5

        # Extract complexity score - look for the FIRST single digit at the start of line
        # or just the number itself (to avoid matching numbers in example text like "Level 5")
        lines = content.strip().split('\n')
        score = None

        # Try to find a standalone number (1-10) as the first non-empty token
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue

            # Check if line starts with a number followed by whitespace/punctuation/end
            match = re.match(r'^(\d+)', stripped)
            if match:
                candidate = int(match.group(1))
                if 1 <= candidate <= 10:
                    score = candidate
                    break
            elif stripped.isdigit():
                # Line is just a number
                candidate = int(stripped)
                if 1 <= candidate <= 10:
                    score = candidate
                    break

        if score is None:
            # Fallback: search for any standalone 1-digit number (prefer digits 1-9 over 10)
            # But exclude matches that are clearly part of level descriptions
            match = re.search(r'(?:^|[^0-9])([1-9])(?:[^0-9]|$)', content[:200])  # Only check first 200 chars
            if match:
                score = int(match.group(1))

        if score is None:
            log(f"[WARN] Judge parsing error: '{content}', defaulting to 5")
            return 5

        return score
    except (ValueError, TypeError) as e:
        log(f"[WARN] Judge parsing error: '{content}', error: {e}, defaulting to 5")
        return 5
    except Exception as e:
        log(f"[WARN] Judge failed ({e}), defaulting to 5")
        return 5


# ─── Proxy to DashScope (transparent passthrough) ────────────────────

async def proxy_to_dashscope(request: Request, model: str, complexity_score: int):
    """Forward request to DashScope and stream the response back verbatim."""
    body_bytes = await request.body()
    body = json.loads(body_bytes)
    body["model"] = model  # override model based on routing decision

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {DASHSCOPE_API_KEY}",
    }

    # Forward any extra headers from the client (except hop-by-hop)
    for k, v in request.headers.items():
        if k.lower() not in ("host", "content-length", "transfer-encoding", "connection"):
            headers[k] = v

    if body.get("stream"):
        # SSE passthrough — truly transparent, byte-for-byte
        async def event_stream():
            client = get_http_client()
            input_tokens = 0
            output_tokens = 0

            try:
                resp = await request_with_retry(
                    client,
                    "post",
                    f"{DASHSCOPE_BASE}/v1/messages",
                    headers,
                    json.dumps(body).encode(),
                    retries=3,
                )

                full_text_parts = []
                async for chunk in resp.aiter_bytes():
                    yield chunk
                    full_text_parts.append(chunk)

                # After stream ends, parse tokens from all chunks
                full_text = b"".join(full_text_parts).decode("utf-8", errors="ignore")

                # Find input_tokens (should appear once in message_start)
                match = re.search(r'"input_tokens"\s*:\s*(\d+)', full_text)
                if match:
                    input_tokens = int(match.group(1))

                # Find output_tokens (last occurrence in message_delta)
                matches = re.findall(r'"output_tokens"\s*:\s*(\d+)', full_text)
                if matches:
                    output_tokens = int(matches[-1])

                log(
                    f"[complexity={complexity_score}/10] upstream_tokens: input={input_tokens}, output={output_tokens}"
                )

            except httpx.ConnectError as e:
                log(f"[ERROR] DashScope connection failed: {e}")
                err = json.dumps({"error": {"type": "connection_error", "message": "Failed to connect to upstream model"}}).encode()
                yield err
            except Exception as e:
                log(f"[ERROR] Stream error: {e}")
                err = json.dumps({"error": {"type": "stream_error", "message": str(e)}}).encode()
                yield err

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            },
        )
    else:
        client = get_http_client()
        try:
            resp = await request_with_retry(
                client,
                "post",
                f"{DASHSCOPE_BASE}/v1/messages",
                headers,
                json.dumps(body).encode(),
                retries=3,
            )
            data = resp.json()
            usage = data.get("usage", {})
            return resp.content, resp.status_code, {
                "input_tokens": usage.get("input_tokens", 0),
                "output_tokens": usage.get("output_tokens", 0),
            }
        except httpx.ConnectError as e:
            log(f"[ERROR] DashScope connection failed: {e}")
            err_content = json.dumps({"error": {"type": "connection_error", "message": "Failed to connect to upstream model"}}).encode()
            return err_content, 502, {"input_tokens": 0, "output_tokens": 0}
        except Exception as e:
            log(f"[ERROR] Non-stream error: {e}")
            err_content = json.dumps({"error": {"type": "request_error", "message": str(e)}}).encode()
            return err_content, 502, {"input_tokens": 0, "output_tokens": 0}


# ─── Routes ──────────────────────────────────────────────────────────

@app.get("/")
async def root():
    return {
        "status": "ok",
        "judge_model": JUDGE_MODEL,
        "cheap_model": CHEAP_MODEL,
        "expensive_model": EXPENSIVE_MODEL,
        "uptime": time.strftime("%Y-%m-%d %H:%M:%S"),
    }


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/v1/messages")
@app.post("/messages")
async def messages(request: Request):
    body = await request.json()
    all_messages = body.get("messages", [])
    system_prompt = body.get("system", "")
    stream = body.get("stream", True)

    # Extract user messages and filter out non-natural-language content
    raw_user_msgs = [m for m in all_messages if m.get("role") == "user"]

    # Filter to only include valid natural language messages
    valid_user_msgs = []
    for i, msg in enumerate(raw_user_msgs):
        extracted_text = await extract_text_content(msg)
        is_valid = is_valid_user_message(extracted_text)
        if is_valid:
            valid_user_msgs.append(msg)

    # Use the LAST valid user message for judging
    if valid_user_msgs:
        final_user_msgs = valid_user_msgs[-1:]
    elif raw_user_msgs:
        final_user_msgs = raw_user_msgs[-1:]
    else:
        final_user_msgs = []

    start = time.time()
    score = await judge_complexity(final_user_msgs, system_prompt)
    judge_time = time.time() - start
    model = EXPENSIVE_MODEL if score >= 6 else CHEAP_MODEL

    log(f"[complexity={score}/10] judge={judge_time:.2f}s → {model}")

    result = await proxy_to_dashscope(request, model, score)

    if isinstance(result, tuple):
        content_or_response, status_code_or_usage, *rest = result
        if isinstance(content_or_response, StreamingResponse):
            # Stream case: (StreamingResponse, usage_holder)
            stream_resp = content_or_response
            # Token usage will be logged when stream finishes
            return stream_resp
        else:
            # Non-stream case: (content, status_code, usage_holder)
            content, status_code, usage_holder = content_or_response, status_code_or_usage, rest[0]
            log(f"  tokens: input={usage_holder['input_tokens']}, output={usage_holder['output_tokens']}")
            return Response(content=content, status_code=status_code, media_type="application/json")
    return result


# ─── Main ────────────────────────────────────────────────────────────

def main():
    port = PORT
    if len(sys.argv) > 1 and sys.argv[1] == "--port":
        port = int(sys.argv[2])

    log(f"Model Router started on {HOST}:{port}")
    log(f"  Cheap model:  {CHEAP_MODEL}")
    log(f"  Expensive model: {EXPENSIVE_MODEL}")
    log(f"  Judge model:  {JUDGE_MODEL} (Ollama :{OLLAMA_PORT})")
    log(f"  DashScope:    {DASHSCOPE_BASE}")
    log("  Press Ctrl+C to stop")

    import uvicorn
    uvicorn.run(app, host=HOST, port=port, log_level="warning")


if __name__ == "__main__":
    main()
