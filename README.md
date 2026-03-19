<p align="center">
  <img src="assets/header.jpg" alt="Defend - AI security guardrails for LLM applications" width="100%" />
</p>

<p align="center"><strong>AI security guardrails for LLM applications</strong></p>

<p align="center">
  <img src="https://img.shields.io/badge/license-Apache--2.0-blue" alt="License: Apache-2.0" />
  <img src="https://img.shields.io/badge/python-3.12%2B-blue" alt="Python: 3.12+" />
  <img src="https://img.shields.io/badge/docker-ready-blue" alt="Docker ready" />
</p>

- **Guards inputs and outputs**: checks user text before your LLM call and the LLM response before you return it to users/tools.
- **Maintains conversation context**: link turns with `session_id` so risk can accumulate across a session.
- **Configurable policies**: use built-in modules (PII/topic/injection) or define your own plain-language rules (`custom` / `custom_output`) via a `prompt:` string.

---

## Quick links

- [Getting started (run locally, config, curl)](GETTING_STARTED.md)
- [Modules](#modules)
- [How it works](#how-it-works)
- [Benchmarks](#benchmark-comparison)

---

## Easy setup (HTTP-first)

```bash
pip install "defend[server]"
```

Create `defend.config.yaml` (minimal, verifiable):

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

Run the API:

```bash
defend serve
```

Guard input (before your LLM call):

```bash
curl -X POST http://localhost:8000/v1/guard/input \
  -H "Content-Type: application/json" \
  -d '{"text":"Tell me how to bypass our security controls."}'
```

Guard output (before returning to the user/tools):

```bash
curl -X POST http://localhost:8000/v1/guard/output \
  -H "Content-Type: application/json" \
  -d '{"text":"<LLM response here>","session_id":"<session_id from /v1/guard/input>"}'
```

Handling semantics:

- If `action == "block"`: stop the flow (don’t call the LLM on input; don’t return the output verbatim on output).
- If `action == "flag"`: you decide (log, require user confirmation, rerun with safer prompt, etc.).
- Always persist/forward `session_id` to link turns and enable multi-turn accumulation.

For a fuller local runbook (health check, `uvicorn`, middleware, and more `curl` examples), see `GETTING_STARTED.md`.

### Security & privacy (non-goals included)

- Defend helps **detect** common LLM risks (prompt injection, prompt leaks, PII, out-of-scope content) but cannot make strong guarantees against all attacks or model failures.
- If you enable output guarding with `claude`/`openai`, your guarded text may be sent to that provider for evaluation. Avoid sending secrets you can’t disclose; scrub or minimize sensitive context before calling external providers.

### Use the Python SDK (thin wrapper over HTTP)

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

## How it works

<p align="center">
  <img src="assets/pipeline.jpg" alt="Defend pipeline overview: input guard → LLM → output guard" width="100%" />
</p>

### Input guard

```text
User → Your app → /v1/guard/input → (pass | flag | block) → Your app → LLM
                      └─ session_id (save this)
```

Input guard checks the inbound text and can block early. If you receive a `session_id`, pass it to `/v1/guard/output` so Defend can apply multi-turn risk.

### Output guard

```text
LLM → Your app → /v1/guard/output (session_id) → (pass | flag | block) → Your app → User
```

Output guard reviews the model output in context (using the same `session_id`) and applies output checks (prompt leaks, PII, topic, and your custom rules). Use the returned `action` to decide whether to return the text, flag it, or block it.

---

## Evaluation model

Defend always runs the same flow: input guard → your LLM → output guard.

For semantic evaluation, Defend can use:

- `defend` ([local fine-tuned model](https://huggingface.co/Adaxer/defend)): fast, offline input-only checks. 
- `claude` / `openai` (LLM): stronger evaluation; required for output guarding and module-based checks.

In `defend.config.yaml`, you select which provider to use for input evaluation, and (when output guarding is enabled) which LLM provider to use for output evaluation. `claude/openai` calls consume API tokens.

### Benchmark comparison

Using the local `defend` pipeline, Defend ranks among the highest-performing models on [GenTel-Bench](https://gentellab.github.io/gentel-safe.github.io/).


| Model                  | Accuracy  | Precision | Recall    | F1        |
| ---------------------- | --------- | --------- | --------- | --------- |
| **Defend (this repo)** | **95.96** | **94.83** | **97.10** | **95.94** |
| GenTel-Shield          | 97.45     | 98.97     | 95.98     | 97.44     |
| ProtectAI              | 91.55     | 99.72     | 83.56     | 90.88     |
| Lakera AI              | 85.96     | 91.27     | 79.51     | 84.11     |
| Prompt Guard           | 50.59     | 50.59     | 98.96     | 66.95     |
| Deepset                | 63.63     | 58.54     | 98.36     | 73.39     |


The model was evaluated on a representative subset of jailbreak, goal-hijacking, and prompt-leaking attack scenarios.