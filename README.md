# Defend

![Defend header](assets/header.jpg)

**AI security guardrails for LLM applications.**

- **Bidirectional**: guard both **input** (before your LLM call) and **output** (before you return text to users or tools).
- **Multi-turn**: join `/v1/guard/input` and `/v1/guard/output` with a `session_id`, with a rolling session risk score used by the pipeline.
- **Plain-language custom rules**: define your own policies via `custom` / `custom_output` using a single `prompt:` string.

![License](https://img.shields.io/badge/license-Apache--2.0-blue)
![Python](https://img.shields.io/badge/python-3.12%2B-blue)
![Docker](https://img.shields.io/badge/docker-ready-blue)

---

## Quick start

```bash
pip install defend
# optional (run the API locally + install FastAPI server deps)
pip install "defend[server]"
```

To run the API locally, add a `defend.config.yaml` in the project root (see `CONFIGURATION.md` or copy from the repo), then:

```bash
defend serve
```

### Use the Python SDK

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

---

## Modules


| Module          | Direction | One-line description                                                               |
| --------------- | --------- | ---------------------------------------------------------------------------------- |
| `injection`     | input     | Detect likely prompt-injection / instruction-override attempts in user text.       |
| `pii`           | input     | Detect user-supplied PII in inbound text.                                          |
| `topic`         | input     | Detect out-of-scope requests vs your configured allowed topics.                    |
| `custom`        | input     | Detect whatever you describe in plain language (`prompt:` string).                 |
| `prompt_leak`   | output    | Detect system prompt / internal instruction exposure in model output.              |
| `pii_output`    | output    | Detect PII leaking in model output.                                                |
| `topic_output`  | output    | Detect out-of-scope responses vs your configured allowed topics.                   |
| `custom_output` | output    | Detect whatever you describe in plain language (`prompt:` string) in model output. |


---

## Pipeline overview

### Input guard

```text
User → Your app → Defend /v1/guard/input → (pass | flag | block) → Your app → LLM
                      └─ returns session_id (use it to link turns)
```

Input evaluation runs through:

- **Normalization**: cleanup, Unicode fixes, whitespace, etc.
- **Intent fast-pass**: quickly pass obviously benign text when enabled.
- **Regex heuristics**: cheap pattern checks for known bad behavior.
- **Semantic provider decision**: call the configured provider chain (`defend`, `claude`, `openai`, or a combo).
- **Session accumulation**: roll up risk across turns when you pass a `session_id`.

### Output guard

```text
LLM → Your app → Defend /v1/guard/output (session_id) → (pass | flag | block) → Your app → User
```

Output evaluation:

- Reuses the **same session** via `session_id`.
- Applies **output modules** (e.g. `prompt_leak`, `pii_output`, `custom_output`).
- Returns the final `action` for your app to enforce.

See `ARCHITECTURE.md` for a deeper, code-first walkthrough.

---

## Provider & chaining model

Defend separates the **pipeline** (what steps run) from **providers** (who makes the semantic decision).

Available providers:

- `**defend`**: local Qwen-based classifier (no external API calls). Input-oriented; ignores modules.
- `**claude` / `openai**`: LLM-backed evaluation; required for output guarding and module-based evaluation.

You choose a provider chain in `defend.config.yaml` (or via the web configurator):

- **Local-only**:
  - `provider.primary: defend`
- **Confidence escalation** (cheap first, pay on uncertainty):
  - `provider.primary: defend`
  - `provider.fallback: claude | openai`
- **Both-active gate** (hard local block before LLM):
  - `provider.primary: claude | openai`
  - `provider.fallback: defend`

Cost note: `defend` costs local compute; `claude`/`openai` calls cost tokens. Escalation/gating lets you control how often you pay for deep evaluation.

See `CONFIGURATION.md` for concrete config examples.

---

## Learn more

- `GETTING_STARTED.md`
- `CONFIGURATION.md`
- `ARCHITECTURE.md`

