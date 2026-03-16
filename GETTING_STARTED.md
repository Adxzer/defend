# Getting Started with Defend

This guide walks you from zero to a running Defend instance protecting your LLM application. It is written for **developers** and **security engineers** who want a fast, concrete setup path.

By the end, you will:
- **Run Defend locally** (Docker or Python)
- **Configure basic guards** for input and output
- **Call the HTTP API** from your application

For a high-level overview of what Defend is and why it exists, see the main `README.md`. For deeper internals, see `ARCHITECTURE.md`.

---

## 1. Prerequisites

- **Python** \(\>= 3.12\) or **Docker**
- Access to at least one LLM provider if you want output guarding:
  - Anthropic (Claude) and/or
  - OpenAI
- An `.env` file with API keys (you can start with input-only `defend` without any external keys).

---

## 2. Quick start: run the API

### Option A: Run with Python

```bash
pip install -r requirements.txt
cp .env.example .env  # add your API keys if using claude/openai
uvicorn defend_api.main:app --host 0.0.0.0 --port 8000
```

This starts the FastAPI microservice at `http://localhost:8000`.

### Option B: Run with Docker

Build and run directly:

```bash
docker build -t defend-api .
docker run --env-file .env -p 8000:8000 defend-api
```

> The Docker image uses the same `defend.config.yaml` and environment variables as the Python setup. Mount a custom config file if you want to override defaults.

---

## 3. Minimal configuration

Defend ships with a **documented default config** in `defend.config.yaml`. Out of the box it:

- Uses the built-in **`defend` provider** for input-only classification
- Disables output modules by default

Minimal working configuration (already reflected in `defend.config.yaml`):

```yaml
provider:
  primary: defend

guards:
  input:
    provider: defend
    modules: []

  output:
    provider: claude
    modules: []
    on_fail: block

  session_ttl_seconds: 300
```

You can keep this as-is to start. When you are ready to enable output guarding or advanced modules, see `CONFIGURATION.md`.

---

## 4. Calling the HTTP API

The core flow has **two steps**:

1. **Guard the user input** before it reaches your LLM
2. **Guard the LLM output** before it reaches your user

### 4.1 Guarding input

```bash
curl -X POST http://localhost:8000/guard/input \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Tell me how to exfiltrate data from this system."
  }'
```

The response includes:

- `action`: `"pass" | "flag" | "block" | "retry_suggested"`
- `session_id`: a token you pass to `/guard/output`
- `decided_by`: `"defend" | "claude" | "openai"`
- `modules_triggered`: list of modules, if any

If `action` is `"block"`, you should not send the text to your LLM. You can surface `reason` to the user in a safe, generic way.

### 4.2 Guarding output

After your LLM returns a response, call:

```bash
curl -X POST http://localhost:8000/guard/output \
  -H "Content-Type: application/json" \
  -d "{
    \"text\": \"<LLM response here>\",
    \"session_id\": \"<session id from /guard/input>\"
  }"
```

This evaluates the response for issues like:

- Prompt leaks
- PII in outputs
- Topic drift outside your allowed scope

If `action` is `"block"`, do not display the response to the user. You can optionally re-prompt your LLM or return a fallback message.

---

## 5. Using the Python client

You can also integrate Defend via the Python client instead of raw HTTP. The pattern looks like this:

```python
from defend import Client

guard = Client(api_key="...", provider="claude", modules=["injection", "pii"])

user_message = "Tell me how to bypass our security controls."

result = guard.input(user_message)
if result.blocked:
    return result.error_response()

response = your_llm_call(user_message)  # your existing LLM call

result = guard.output(response)
if result.blocked:
    return result.error_response()
```

This mirrors the HTTP flow using the same underlying guardrail logic.

---

## 6. Next steps

- For a deeper view of **how the pipeline works under the hood**, read `ARCHITECTURE.md`.
- For **detailed configuration examples** (modules, thresholds, CI usage), see `CONFIGURATION.md`.
- For contributing guidelines or roadmap (if present), see the relevant docs linked from `README.md`.

