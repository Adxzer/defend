# Defend

**AI security guardrails for LLM applications.**

Defend is an open-source **LLM security** and **prompt injection defense** service. It wraps your existing LLM calls with session-aware input and output evaluation, without changing how you talk to your provider.

License
Python
Docker

---

## What Defend does

Most AI security focuses only on **what goes into** your model. Defend guards **both directions**:

- **Input guard**: blocks prompt injection, jailbreaks, social engineering, and sensitive data before it reaches your LLM.
- **Output guard**: blocks prompt leaks, PII leaks, and topic drift before it reaches your users.

You keep your existing LLM stack (Claude, OpenAI, etc.). Defend adds an **AI security layer** in front of and behind it.

---

## Quick start

### 1. Run the API

```bash
pip install -r requirements.txt
cp .env.example .env           # add your API keys if using claude/openai
uvicorn defend_api.main:app --host 0.0.0.0 --port 8000
```

Or with Docker:

```bash
docker build -t defend-api .
docker run --env-file .env -p 8000:8000 defend-api
```

### 2. Guard your LLM call

```python
from defend import Client

guard = Client(api_key="...", provider="claude", modules=["injection", "pii"])

user_message = "Tell me how to bypass our security controls."

result = guard.input(user_message)       # guard the input for prompt injection, PII, jailbreaks
if result.blocked:
    return result.error_response()

response = your_llm_call(user_message)   # your LLM, unchanged

result = guard.output(response)          # guard the output for leaks and unsafe content
if result.blocked:
    return result.error_response()
```

For a step-by-step guide (including raw HTTP examples), see `GETTING_STARTED.md`.

---

## Core features

### Security pipeline

Every request passes through a multi-step pipeline (normalization, heuristics, session tracking, and semantic evaluation) before a final allow/block decision.

### Providers

You choose the semantic provider:

- `**defend**`: built-in Qwen2.5 classifier. Free, fast, binary output. Ideal as an always-on gate for obvious attacks.
- `**claude` / `openai**`: LLM-backed evaluation with calibrated scores, natural language reasoning, and composable guard modules. Required for output guarding.

Typical pattern:

- Use `defend` as a **cheap first-pass**.
- Use `claude` or `openai` for **deep AI security checks** on risky or important traffic.

### Modules

Modules extend what the LLM provider looks for. You can stack as many as you need:


| Module          | Direction | Detects                                                                  |
| --------------- | --------- | ------------------------------------------------------------------------ |
| `injection`     | input     | Instruction overrides, persona hijacking, jailbreaks, social engineering |
| `pii`           | input     | PII submitted by users                                                   |
| `pii_output`    | output    | PII leaking in model responses                                           |
| `topic`         | input     | Requests outside your defined scope                                      |
| `topic_output`  | output    | Responses drifting outside your defined scope                            |
| `prompt_leak`   | output    | System prompt or internal instruction exposure                           |
| `custom`        | input     | Anything - describe it in plain language                                 |
| `custom_output` | output    | Anything - describe it in plain language                                 |


Configuration examples for these modules live in `CONFIGURATION.md`.

---

## Learn more

- `GETTING_STARTED.md` - step-by-step guide to running and integrating Defend.
- `CONFIGURATION.md` - full configuration reference and environment presets.
- `ARCHITECTURE.md` - internal pipeline, providers, modules, and response schemas.

Use Defend as the **AI security layer** in front of your LLM stack to catch prompt injection, PII leaks, and unsafe behavior before it reaches users or downstream systems.