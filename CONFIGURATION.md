# Configuration

This file documents what the server actually reads today (`defend/api/config.py`). If a knob isn’t here, don’t assume it exists.

## Where config lives

The API loads `defend.config.yaml` from the repository root at startup. Create this file by copying the example in the repo or by hand using the schema below.

## Providers

Config shape:

```yaml
provider:
  primary: defend   # defend | claude | openai
```

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

## Provider model overrides

Claude/OpenAI providers have built-in defaults, but you can override the model IDs:

```yaml
models:
  claude: "claude-3-5-sonnet-20241022"
  openai: "gpt-4.1-mini"
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
    enabled: true
    provider: claude   # must be claude or openai
    modules: []
    on_fail: block     # block | flag | retry_suggested

  session_ttl_seconds: 300
```

Key behaviors:

- `guards.output.provider` is validated to **only** allow `claude` or `openai` (startup fails otherwise).
- If `guards.output.enabled: false`, `/v1/guard/output` short-circuits to `action: pass` (useful for defend-only setups).
- `session_ttl_seconds` controls how long input context is kept for `/v1/guard/output` lookups (in-memory, per-process).

## Init token (CLI)

You can generate a shareable compressed init token from an existing config:

```bash
defend init --from-config
```

And you can apply a token to write a new `defend.config.yaml`:

```bash
defend init --token "<defend_v1_...>"
```

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
    enabled: false
    provider: claude
    modules: []
    on_fail: block
```
