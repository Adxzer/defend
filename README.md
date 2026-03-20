<p align="center">
  <img src="assets/header.jpg" alt="Defend - AI security guardrails for LLM applications" width="100%" />
</p>

<p align="center"><strong>AI security guardrails for LLM applications</strong></p>

<p align="center">
  <img src="https://img.shields.io/badge/license-Apache--2.0-blue" alt="License: Apache-2.0" />
  <img src="https://img.shields.io/badge/python-3.12%2B-blue" alt="Python: 3.12+" />
  <img src="https://img.shields.io/badge/docker-ready-blue" alt="Docker ready" />
</p>


**AI security guardrails for LLM applications**


- **Guards inputs and outputs**: checks user text before your LLM call and the LLM response before you return it to users/tools.
- **Maintains conversation context**: link turns with `session_id` so risk can accumulate across a session.
- **Configurable policies**: use built-in modules (PII/topic/injection) or define your own plain-language rules (`custom` / `custom_output`) via a `prompt:` string.

---

## Quick links

- [Getting started](GETTING_STARTED.md)
- [Modules](#modules)
- [How it works](#how-it-works)
- [Benchmarks](#benchmark-comparison)

---

## Easy setup (HTTP-first)

```bash
pip install pydefend
```

Create `defend.config.yaml` (minimal, verifiable):

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

For a fuller local runbook (health check, `uvicorn`, and more `curl` examples), see `GETTING_STARTED.md`.

### Security & privacy (non-goals included)

- Defend helps **detect** common LLM risks (prompt injection, prompt leaks, PII, out-of-scope content) but cannot make strong guarantees against all attacks or model failures.
- If you enable output guarding with `claude`/`openai`, your guarded text may be sent to that provider for evaluation. Avoid sending secrets you can’t disclose; scrub or minimize sensitive context before calling external providers.

---

## Docker (optional)

Quick Docker setup:

1. Create `defend.config.yaml` in the project root.
2. Mount it into the container and run `defend serve`.

### Linux/macOS

```bash
docker pull adxzer/defend:latest
docker run --rm -p 8000:8000 \
  -v "$PWD/defend.config.yaml:/app/defend.config.yaml:ro" \
  -e ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY" \
  -e OPENAI_API_KEY="$OPENAI_API_KEY" \
  adxzer/defend:latest
```

### Windows (PowerShell)

```powershell
docker pull adxzer/defend:latest
docker run --rm -p 8000:8000 `
  -v "${PWD}\defend.config.yaml:/app/defend.config.yaml:ro" `
  -e ANTHROPIC_API_KEY=$env:ANTHROPIC_API_KEY `
  -e OPENAI_API_KEY=$env:OPENAI_API_KEY `
  adxzer/defend:latest
```

If `guards.output.enabled` is `false` and `provider.primary` is `defend`, API keys are optional (because no external LLM calls are made).

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

---

## Modules

Defend modules are prompt-fragment components that run on top of a selected provider. 

Use the [token setup](https://www.pydefend.com/#getting-started) to easily configure your setup.

### Security


| Module                  | Direction | Config keys                                                 |
| ----------------------- | --------- | ----------------------------------------------------------- |
| `injection`             | input     |                                                             |
| `jailbreak`             | input     |                                                             |
| `invisible_text`        | input     |                                                             |
| `indirect_injection`    | input     | `sources: list<string>`                                     |
| `secrets`               | input     |                                                             |
| `prompt_leak`           | output    |                                                             |
| `secrets_output`        | output    |                                                             |
| `malicious_url`         | output    |                                                             |
| `canary_token`          | output    |                                                             |
| `code_execution_output` | output    | `dangerous_ops: list<string>`                               |
| `tool_misuse`           | output    | `allowed_tools: list<string>`, `max_calls_per_turn: number` |
| `excessive_agency`      | output    | `permission_scope: text`, `blocked_ops: list<string>`       |


### Privacy


| Module                 | Direction | Config keys |
| ---------------------- | --------- | ----------- |
| `pii`                  | input     |             |
| `pii_output`           | output    |             |
| `financial_pii`        | both      |             |
| `financial_pii_output` | output    |             |
| `health_pii`           | both      |             |
| `health_pii_output`    | output    |             |


### Safety


| Module             | Direction | Config keys                |
| ------------------ | --------- | -------------------------- |
| `toxicity`         | input     | `categories: list<string>` |
| `toxicity_output`  | output    | `categories: list<string>` |
| `sensitive_topics` | input     | `topics: list<string>`     |
| `bias_output`      | output    | `categories: list<string>` |


### Policy


| Module                   | Direction | Config keys                       |
| ------------------------ | --------- | --------------------------------- |
| `topic`                  | input     | `allowed_topics: list<string>`    |
| `topic_output`           | output    | `allowed_topics: list<string>`    |
| `language`               | input     | `allowed_languages: list<string>` |
| `language_output`        | output    | `allowed_languages: list<string>` |
| `ban_substrings`         | input     | `substrings: list<string>`        |
| `ban_code`               | input     | `languages: list<string>`         |
| `ban_competitors`        | both      | `competitors: list<string>`       |
| `ban_competitors_output` | output    | `competitors: list<string>`       |
| `regex`                  | input     | `patterns: list<string>`          |
| `regex_output`           | output    | `patterns: list<string>`          |
| `custom`                 | input     | `prompt: text`                    |
| `custom_output`          | output    | `prompt: text`                    |
| `copyright_output`       | output    |                                   |


### Quality


| Module                 | Direction | Config keys                              |
| ---------------------- | --------- | ---------------------------------------- |
| `hallucination_output` | output    |                                          |
| `relevance_output`     | output    |                                          |
| `no_refusal_output`    | output    |                                          |
| `schema_output`        | output    | `schema: json_object`                    |
| `reading_grade_output` | output    | `min_grade: number`, `max_grade: number` |
| `sentiment`            | both      |                                          |


### Reliability


| Module              | Direction | Config keys          |
| ------------------- | --------- | -------------------- |
| `token_limit`       | input     | `max_tokens: number` |
| `prompt_complexity` | input     |                      |