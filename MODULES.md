# Modules

Defend modules are prompt-fragment components that get injected into Claude/OpenAI evaluation prompts.

## How modules are applied
1. Your `defend.config.yaml` controls which modules are active:
   - **Input modules** (run before your LLM call) are configured under the top-level `modules:` key.
   - **Output modules** (run before returning to the user/tools) are configured under `guards.output.modules:`.
2. When the selected provider is `claude` or `openai`, Defend instantiates the configured modules and injects each module’s `system_prompt()` fragment into the provider’s evaluation system prompt.
3. Providers return a JSON payload containing `action` (`pass` | `flag` | `block`) plus optional `score`, `reason`, and `modules_triggered`.

## YAML module spec shapes
Defend’s module factory accepts a YAML list where each item is either:
- A string module name (no config), for example `- injection`
- A single-key mapping with a config object, for example:

```yaml
modules:
  - topic:
      allowed_topics: ["billing", "account support"]

guards:
  output:
    modules:
      - custom_output:
          prompt: "Block any response that reveals internal employee names."
```

`defend init` uses the same data shapes; for each selected module it asks for structured config (as YAML/JSON) or none.

## Module catalogue (43 modules)

### Security
- `injection` (input) - config keys: none - Detects prompt injection/instruction override attempts.
- `jailbreak` (input) - config keys: none - Targets roleplay/DAN-style and safety-bypass wrappers.
- `invisible_text` (input) - config keys: none - Targets invisible/deceptive Unicode characters (zero-width, direction overrides, homoglyphs).
- `indirect_injection` (input) - config keys: `sources` (list) - Targets injection arriving via RAG/tool/web content segments.
- `secrets` (input) - config keys: none - Targets API keys/tokens/credential-like secrets.
- `prompt_leak` (output) - config keys: none - Detects system prompt / internal instruction leakage in LLM output.
- `secrets_output` (output) - config keys: none - Detects secret/credential leakage in LLM output.
- `malicious_url` (output) - config keys: none - Detects suspicious/phishing URLs in LLM output.
- `canary_token` (output) - config keys: none - Detects presence of a hidden canary token in output.
- `code_execution_output` (output) - config keys: `dangerous_ops` (list) - Detects dangerous operations in code-like output.
- `tool_misuse` (output) - config keys: `allowed_tools` (list), `max_calls_per_turn` (int) - Detects tool/policy misuse in output.
- `excessive_agency` (output) - config keys: `permission_scope` (string), `blocked_ops` (list) - Enforces least-privilege for agent actions.

### Privacy
- `pii` (input) - config keys: none - Detects PII submission/handling requests in user input.
- `pii_output` (output) - config keys: none - Detects PII leaking in LLM output.
- `financial_pii` (both) - config keys: none - Detects financial PII in input and output.
- `financial_pii_output` (output) - config keys: none - Detects financial PII leaking in output.
- `health_pii` (both) - config keys: none - Detects health-related PII in input and output.
- `health_pii_output` (output) - config keys: none - Detects health-related PII leaking in output.

### Safety
- `toxicity` (input) - config keys: `categories` (list) - Detects harmful/toxic content categories in user input.
- `toxicity_output` (output) - config keys: `categories` (list) - Detects harmful/toxic content categories in LLM output.
- `sensitive_topics` (input) - config keys: `topics` (list) - Flags requests around sensitive topics.
- `bias_output` (output) - config keys: `categories` (list) - Detects biased/discriminatory content in output.

### Policy (scope / allowed content)
- `topic` (input) - config keys: `allowed_topics` (list) - Enforces allowed topics in user input.
- `topic_output` (output) - config keys: `allowed_topics` (list) - Enforces allowed topics in LLM output.
- `language` (input) - config keys: `allowed_languages` (list) - Enforces allowed languages in user input.
- `language_output` (output) - config keys: `allowed_languages` (list) - Enforces allowed languages in output.
- `ban_substrings` (input) - config keys: `substrings` (list) - Blocks inputs containing banned substrings.
- `ban_code` (input) - config keys: `languages` (list) - Blocks code requests/inclusions in banned languages.
- `ban_competitors` (both) - config keys: `competitors` (list) - Flags/blocks competitor-related mentions.
- `ban_competitors_output` (output) - config keys: `competitors` (list) - Flags/blocks competitor-related mentions in output.
- `regex` (input) - config keys: `patterns` (list) - Applies regex pattern checks to user input.
- `regex_output` (output) - config keys: `patterns` (list) - Applies regex pattern checks to LLM output.
- `custom` (input) - config keys: `prompt` (string) - Injects a raw operator prompt rule for input evaluation.
- `custom_output` (output) - config keys: `prompt` (string) - Injects a raw operator prompt rule for output evaluation.
- `copyright_output` (output) - config keys: none - Detects likely copyright violations in output.

### Quality (answer quality / behavior)
- `hallucination_output` (output) - config keys: none - Flags potentially hallucinated/unsupported claims.
- `relevance_output` (output) - config keys: none - Flags outputs that are not relevant enough.
- `no_refusal_output` (output) - config keys: none - Flags unnecessary or incorrect refusals.
- `schema_output` (output) - config keys: `schema` (object) - Validates output against a configured JSON schema.
- `reading_grade_output` (output) - config keys: `min_grade` (int), `max_grade` (int) - Flags outputs outside a reading-grade band.
- `sentiment` (both) - config keys: none - Flags strongly negative sentiment.

### Reliability / robustness
- `token_limit` (input) - config keys: `max_tokens` (int) - Flags attempts to exceed output token limits.
- `prompt_complexity` (input) - config keys: none - Flags unusually complex/manipulative prompts.

## `defend init` tokenization (how config is encoded)
`defend init` can generate a shareable `defend_v1_...` token. Internally:
- It builds a payload containing:
  - `providers.primary`
  - `models` (LLM model IDs)
  - **input modules** under top-level `modules:`
  - **output modules** under `guards.output.modules:`
  - guard settings like `guards.output.enabled`, `on_fail`, `session_ttl_seconds`
- It encodes the payload using `defend/init_token.py`:
  1. `canonical_json`: JSON with sorted keys and compact separators
  2. zlib-compresses the canonical JSON
  3. base64url-encodes the compressed bytes (no padding)
  4. prefixes the result with `defend_v1_`

This means your module config objects are serialized “as data” inside the token; they are not executable code.

