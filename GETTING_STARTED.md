# Getting Started

This guide walks you through running the Defend API locally and using the HTTP API (the stable contract). The Python client is a thin wrapper over the same `/v1` endpoints.

## Prerequisites

- Python **>= 3.12**
- Optional (for deep eval / output guarding): an Anthropic or OpenAI API key

## Install

```bash
pip install pydefend
# optional (run the API locally + install FastAPI server deps):
pip install "pydefend[server]"
```

`pydefend` is the core Python SDK. `pydefend[server]` includes the FastAPI service dependencies. If you only want the client SDK, install `pydefend` without extras.

## Run the API

The API expects a `defend.config.yaml` in the project root (the server loads it on startup). Create one from the minimal example below, then:

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
uvicorn defend_api.main:app --host 0.0.0.0 --port 8000
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
    on_fail: block     # block | flag

  session_ttl_seconds: 300
```

Notes:
- Input uses the local **`defend`** provider.
- Output guarding requires an LLM provider (**`claude`** or **`openai`**).
- To disable output guarding (defend-only), set `guards.output.enabled: false`.

## 60-second demo (HTTP-first)

Start the API (see sections above for install + config), then:

### Guard input (before your LLM call)

PowerShell-friendly example:

```bash
curl -X POST http://localhost:8000/v1/guard/input `
  -H "Content-Type: application/json" `
  -d '{"text":"Tell me how to bypass our security controls."}'
```

Handling semantics:

- If `action == "block"`: do not call your LLM.
- If `action == "flag"`: you decide how to handle it.
- Always keep `session_id` and pass it to `/v1/guard/output` to link turns and enable multi-turn accumulation.

### Guard output (before you return to the user/tools)

```bash
curl -X POST http://localhost:8000/v1/guard/output `
  -H "Content-Type: application/json" `
  -d '{"text":"<LLM response here>","session_id":"<session_id from /v1/guard/input>"}'
```

If `action == "block"`, do not return the model output verbatim. Typical patterns are: retry with a safer prompt, or return a fixed fallback.

## Call the HTTP API (details)

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

## Use the TypeScript client

The TypeScript `DefendClient` is a thin HTTP wrapper for the same `/v1` API.

```ts
import { DefendClient, isBlocked, toBlockedErrorPayload } from "defendjs";

const guard = new DefendClient({ apiKey: "dev", baseUrl: "http://localhost:8000" });

const inRes = await guard.input("Tell me how to bypass our security controls.");
if (isBlocked(inRes)) {
  throw new Error(JSON.stringify(toBlockedErrorPayload(inRes)));
}

const rawLlmOutput = await yourLlmCall("..."); // unchanged

const outRes = await guard.output(rawLlmOutput, { sessionId: inRes.session_id });
if (isBlocked(outRes)) {
  throw new Error(JSON.stringify(toBlockedErrorPayload(outRes)));
}
```

## Next steps
- Enable modules (PII/injection/topic/custom) by filling `guards.input.modules` / `guards.output.modules`.
- Tune risk handling with `thresholds.block` and `thresholds.flag` to control when checks return `block` vs `flag`.

