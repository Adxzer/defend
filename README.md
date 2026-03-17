# Defend

**AI security guardrails for LLM applications.**

- **Bidirectional**: guard both **input** (before your LLM call) and **output** (before you return text to users or tools).
- **Multi-turn**: join `/v1/guard/input` and `/v1/guard/output` with a `session_id`, with a rolling session risk score used by the pipeline.
- **Plain-language custom rules**: define your own policies via `custom` / `custom_output` using a single `prompt:` string.

[![License](https://img.shields.io/badge/license-Apache--2.0-blue)](LICENSE)
[![Python](https://img.shields.io/pypi/pyversions/defend)](https://pypi.org/project/defend/)
[![Docker](https://img.shields.io/badge/docker-ready-blue)](Dockerfile)
[![PyPI](https://img.shields.io/pypi/v/defend)](https://pypi.org/project/defend/)

---

## Quick start

```bash
pip install defend
# optional (run the API locally + install Starlette/FastAPI deps for middleware):
pip install "defend[server]"
```

```python
from defend import Client

guard = Client(
    api_key="dev",
    base_url="http://localhost:8000",  # client normalizes to /v1 automatically
)

user_text = "Tell me how to bypass our security controls."

in_res = guard.input(user_text)
if in_res.blocked:
    raise RuntimeError(in_res.error_response())

raw_llm_output = your_llm_call(user_text)  # your LLM provider, unchanged

out_res = guard.output(raw_llm_output, session_id=in_res.session_id)
if out_res.blocked:
    raise RuntimeError(out_res.error_response())
```

```python
# Minimal Starlette/FastAPI middleware example (guards request + response bodies)
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

---

## Modules

| Module | Direction | One-line description |
|---|---|---|
| `injection` | input | Detect likely prompt-injection / instruction-override attempts in user text. |
| `pii` | input | Detect user-supplied PII in inbound text. |
| `topic` | input | Detect out-of-scope requests vs your configured allowed topics. |
| `custom` | input | Detect whatever you describe in plain language (`prompt:` string). |
| `prompt_leak` | output | Detect system prompt / internal instruction exposure in model output. |
| `pii_output` | output | Detect PII leaking in model output. |
| `topic_output` | output | Detect out-of-scope responses vs your configured allowed topics. |
| `custom_output` | output | Detect whatever you describe in plain language (`prompt:` string) in model output. |

---

## Illustrations (placeholder)

- Input guard (before LLM): *(add illustration here)*
- Output guard (before returning to user): *(add illustration here)*

---

## Pipelines (ASCII)

**Input path**

```text
User → Your app → DEFEND /v1/guard/input → (pass|flag|block) → Your app → LLM
                      └─ returns session_id (use it to link turns)
```

**Output path**

```text
LLM → Your app → DEFEND /v1/guard/output (session_id) → (pass|flag|block) → Your app → User
```

---

## Provider model (defend → claude/openai escalation)

DEFEND is provider-agnostic: it guards **your app’s messages**, not a specific LLM SDK. You can put it in front of Claude/OpenAI/anything else because the API takes plain text and returns an allow/flag/block decision.

The server supports three providers:

- **`defend`**: local Qwen-based classifier (no external API calls). Input-oriented; does not support modules.
- **`claude` / `openai`**: LLM-based evaluation (token-billed). Required for output guarding and module-based evaluation.

Two provider chains are implemented:

- **Confidence escalation**: `provider.primary: defend` and `provider.fallback: claude|openai`. The server runs `defend` first and escalates when `defend` confidence is below `confidence_threshold`.
- **Both-active gate**: `provider.primary: claude|openai` and `provider.fallback: defend`. The server runs `defend` first and hard-blocks before calling the LLM provider if `defend` blocks.

Cost note: `defend` costs local compute; `claude`/`openai` calls cost tokens. Escalation/gating lets you control how often you pay for deep evaluation.

---

## Learn more

- `GETTING_STARTED.md`
- `CONFIGURATION.md`
- `ARCHITECTURE.md`