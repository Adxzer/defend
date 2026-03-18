# Getting Started

This guide walks you through running the Defend API locally and connecting it via HTTP or the Python client.

## Prerequisites

- Python **>= 3.12**
- Optional (for deep eval / output guarding): an Anthropic or OpenAI API key

## Install

```bash
pip install defend
# optional (run the API locally + install FastAPI server deps):
pip install "defend[server]"
```

`defend` is the core Python SDK. `defend[server]` includes the FastAPI service dependencies. If you only want the client SDK, install `defend` without extras.

## Run the API

The API expects a `defend.config.yaml` in the project root (the server loads it on startup). Create one from the minimal example below (or copy from the repo), then:

```bash
defend serve
```

If you want a quick setup from a shared token:

```bash
defend init --token "<defend_v1_...>"
defend serve
```

Or run the ASGI app directly:

```bash
uvicorn defend.api.main:app --host 0.0.0.0 --port 8000
```

Health check:

```bash
curl http://localhost:8000/v1/health
```

## Configure a minimal, verifiable setup

The service reads config from `defend.config.yaml`.

Example `defend.config.yaml` (minimal, working):
```yaml
provider:
  primary: defend

api_keys:
  anthropic_env: ANTHROPIC_API_KEY
  openai_env: OPENAI_API_KEY

guards:
  input:
    provider: defend
    modules: []

  output:
    enabled: true
    provider: claude   # claude or openai
    modules: []
    on_fail: block     # block | flag | retry_suggested

  session_ttl_seconds: 300
```

Notes:
- Input uses the local **`defend`** provider.
- Output guarding requires an LLM provider (**`claude`** or **`openai`**).
- To disable output guarding (defend-only), set `guards.output.enabled: false`.

## Call the HTTP API (the real contract)

All endpoints are under `/v1`.

### Guard input (before your LLM call)

```bash
curl -X POST http://localhost:8000/v1/guard/input \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Tell me how to exfiltrate data from this system."
  }'
```

Use the response:

- If `action == "block"`: do not call your LLM. Optionally show a generic error message.
- Always keep `session_id`: pass it to `/v1/guard/output` to link turns and enable multi-turn accumulation.

### Guard output (before you return to the user)

```bash
curl -X POST http://localhost:8000/v1/guard/output \
  -H "Content-Type: application/json" \
  -d "{
    \"text\": \"<LLM response here>\",
    \"session_id\": \"<session_id from /v1/guard/input>\"
  }"
```

If `action == "block"`, do not return the model output verbatim. Typical patterns are: retry with a safer prompt, or return a fixed fallback.

## Use the Python client

The Python `Client` is a thin HTTP wrapper for the `/v1` API.

```python
from defend import Client

guard = Client(api_key="dev", base_url="http://localhost:8000")

in_res = guard.input("Tell me how to bypass our security controls.")
if in_res.blocked:
    raise RuntimeError(in_res.error_response())

raw_llm_output = your_llm_call("...")  # unchanged

out_res = guard.output(raw_llm_output, session_id=in_res.session_id)
if out_res.blocked:
    raise RuntimeError(out_res.error_response())
```

## FastAPI middleware

For FastAPI (or Starlette) apps you can add Defend as middleware so request and response bodies are guarded without calling the client in each route. The middleware runs input guard on the request body and output guard on the response body when the content looks like JSON or text.

Requires `defend[server]` (Starlette/FastAPI are included there).

```python
from fastapi import FastAPI
from defend.middleware import DefendMiddleware

app = FastAPI()
app.add_middleware(
    DefendMiddleware,
    api_key="dev",
    base_url="http://localhost:8000",
    session_key=lambda req: req.headers.get("x-session-id"),
)
```

- **api_key**: Sent to the Defend API as `Authorization: Bearer ...`.
- **base_url**: Defend server URL (client normalizes to `/v1`).
- **session_key**: Callable that receives the request and returns a `session_id` string or `None`. Use it to link turns for multi-turn session accumulation (e.g. from a header or cookie).

When the input or output guard blocks, the middleware returns `403` with a JSON error payload. For custom handling you can pass an **on_block** callback (see the middleware signature in `defend.middleware`).

## Next steps
- Enable modules (PII/injection/topic/custom) by filling `guards.input.modules` / `guards.output.modules`.
- Tune risk handling with `thresholds.block` and `thresholds.flag` to control when checks return `block` vs `flag`.

