# Defend

**The guardrail layer your LLM stack is missing.**

![License](https://img.shields.io/badge/license-Apache--2.0-blue)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![Docker](https://img.shields.io/badge/docker-ready-blue)

Most LLM security stops at the input. Defend guards both directions - wrapping your existing LLM call with session-aware input and output evaluation, without ever touching the LLM call itself.
```python
guard = defend.Client(api_key="...", provider="claude", modules=["injection", "pii"])

result = guard.input(user_message)       # block prompt injection, PII, jailbreaks
if result.blocked:
    return result.error_response()

response = your_llm_call(user_message)   # your LLM, unchanged

result = guard.output(response)          # block prompt leaks, PII in responses
if result.blocked:
    return result.error_response()
```

That's the whole integration. Defend never makes the LLM call — you own that.

---

## How it works

Every request passes through a six-layer preprocessing pipeline (normalization, intent fast-pass, regex heuristics, perplexity filter, session accumulation) before reaching the semantic provider layer. You choose the provider.

**`defend`** — a built-in fine-tuned Qwen2.5 classifier. Free, fast, binary output. No external API calls. Good for catching obvious attacks at the gate.

**`claude` / `openai`** — LLM-backed evaluation with calibrated scores, natural language reasoning, and composable guard modules. Required for output guarding.

Run both together: `defend` blocks obvious attacks for free, the LLM provider handles everything that needs judgment.

---

## Modules

Modules extend the LLM provider's evaluation. Stack as many as you need.

| Module | Direction | Detects |
|---|---|---|
| `injection` | input | Instruction overrides, persona hijacking, jailbreaks, social engineering |
| `pii` | input | PII submitted by users |
| `pii_output` | output | PII leaking in model responses |
| `topic` | input | Requests outside your defined scope |
| `topic_output` | output | Responses drifting outside your defined scope |
| `prompt_leak` | output | System prompt or internal instruction exposure |
| `custom` | input | Anything — describe it in plain language |
| `custom_output` | output | Anything — describe it in plain language |

---

## Self-hosted
```bash
pip install -r requirements.txt
cp .env.example .env           # add your API keys
uvicorn defend_api.main:app --host 0.0.0.0 --port 8000
```

Configure providers and modules in `defend.config.yaml`. Redis is required for session state.
```yaml
guards:
  input:
    provider: defend
  output:
    provider: claude
    modules: [prompt_leak, pii_output]
```

---

## API

| Endpoint | Description |
|---|---|
| `POST /guard/input` | Evaluate user input, return verdict + `session_id` |
| `POST /guard/output` | Evaluate LLM response, optionally with input context |
| `GET /health` | Health check |
| `GET /ready` | Readiness check (models + Redis) |
| `GET /metrics` | Prometheus metrics |

---

See `ARCHITECTURE.md` for the full pipeline, provider system, and response schemas.