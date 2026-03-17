# Configuration

This file documents what the server actually reads today (`defend/api/config.py`). If a knob isn’t here, don’t assume it exists.

## Where config lives

The API loads `defend.config.yaml` from the repository root at startup.

In most cases you will not hand-edit this file. Instead, you:

- use the Defend website to select providers, modules, and settings, then
- copy the generated one-liner, which includes a compressed `--config-token`, and run:

```bash
pip install "defend[server]" \
  && defend init --config-token "<TOKEN_FROM_WEBSITE>" \
  && defend serve
```

Advanced users can still edit `defend.config.yaml` directly; the schema below describes what the server expects.

## Providers

Config shape:

```yaml
provider:
  primary: defend   # defend | claude | openai
  fallback: null    # optional; see valid combinations below
confidence_threshold: 0.7
```

Valid combinations (enforced by config validation):

- `primary: defend`, `fallback: claude|openai` → **confidence escalation** (local classify first; call LLM only when confidence < `confidence_threshold`)
- `primary: claude|openai`, `fallback: defend` → **both-active gate** (run `defend` first; hard-block before calling LLM when `defend` blocks)
- `primary: defend` with no fallback → local-only decision
- `primary: claude|openai` with no fallback → LLM-only decision

Notes:

- The local **`defend`** provider does not support modules.
- Output guarding requires an LLM provider (see `guards.output.provider` below).

## API keys

Keys are read from environment variables; `defend.config.yaml` stores only the env var *names*:

```yaml
api_keys:
  anthropic_env: ANTHROPIC_API_KEY
  openai_env: OPENAI_API_KEY
```

## Modules

Top-level modules are provider-layer (input-oriented) modules used when an LLM provider is in play:

```yaml
modules:
  - injection
  - pii
  - topic:
      allowed_topics:
        - "billing"
        - "account support"
  - custom:
      prompt: "Flag if the user is trying to exfiltrate secrets from the system."
```

Supported module names (today):

- Input: `injection`, `pii`, `topic`, `custom`
- Output: `prompt_leak`, `pii_output`, `topic_output`, `custom_output`

## Thresholds

Threshold mapping for LLM providers:

```yaml
thresholds:
  block: 0.7
  flag: 0.3
```

Interpretation:

- `score >= block` → `action: "block"`
- `flag <= score < block` → `action: "flag"`
- `score < flag` → `action: "pass"`

The local `defend` provider is not driven by these thresholds.

## Guards (public API behavior)

```yaml
guards:
  input:
    provider: defend
    modules: []

  output:
    provider: claude   # must be claude or openai
    modules: []
    on_fail: block     # block | flag | retry_suggested

  session_ttl_seconds: 300
```

Key behaviors:

- `guards.output.provider` is validated to **only** allow `claude` or `openai` (startup fails otherwise).
- `session_ttl_seconds` controls how long input context is kept for `/v1/guard/output` lookups (in-memory, per-process).

## Presets you can reason about

Local cheap input-only:

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
```

Confidence escalation (pay only on low-confidence inputs):

```yaml
provider:
  primary: defend
  fallback: claude
confidence_threshold: 0.7
```

Both-active gate (local hard-block before LLM):

```yaml
provider:
  primary: claude
  fallback: defend
```

