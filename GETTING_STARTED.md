# Getting Started

This guide walks you through running the Defend API locally and using the HTTP API (the stable contract).

## Prerequisites

- Python **>= 3.12**
- Optional (for deep eval / output guarding): an Anthropic or OpenAI API key

## Install

```bash
pip install pydefend
```

`pydefend` installs the API package and CLI, including server dependencies for running `defend serve`.

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

models:
  # Defaults to cheaper models when unset.
  claude: "claude-3-5-haiku-latest"
  openai: "gpt-4o-mini"

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

## Next steps
- Enable modules (PII/injection/topic/custom) by filling `guards.input.modules` / `guards.output.modules`.
- Tune risk handling with `thresholds.block` and `thresholds.flag` to control when checks return `block` vs `flag`.

## Run the API with Docker
Docker runs the API using the root `Dockerfile` (it starts `uvicorn` on port `8000`).

1. Create a `defend.config.yaml` in the project root.
2. Pull the published image from Docker Hub:

```bash
docker pull adxzer/defend:<pydefend_version>
```

3. Run the container (mount your `defend.config.yaml` and pass any required LLM keys):

### Linux/macOS
```bash
docker run --rm -p 8000:8000 \
  -v "$PWD/defend.config.yaml:/app/defend.config.yaml:ro" \
  -e ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY" \
  -e OPENAI_API_KEY="$OPENAI_API_KEY" \
  adxzer/defend:<pydefend_version>
```

### Windows (PowerShell)
```powershell
docker run --rm -p 8000:8000 `
  -v "${PWD}\defend.config.yaml:/app/defend.config.yaml:ro" `
  -e ANTHROPIC_API_KEY=$env:ANTHROPIC_API_KEY `
  -e OPENAI_API_KEY=$env:OPENAI_API_KEY `
  adxzer/defend:<pydefend_version>
```

Health check:
```bash
curl http://localhost:8000/v1/health
```

