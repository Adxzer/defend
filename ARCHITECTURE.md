# Architecture

This is a code-first description of how the DEFEND service behaves today. If you want the “how do I wire this into my app” path, start with `GETTING_STARTED.md`.

## What DEFEND is

DEFEND is a FastAPI service with two public guard endpoints:

- `/v1/guard/input`: evaluate inbound text before you call your LLM.
- `/v1/guard/output`: evaluate outbound text before you return it.

The core contract is explicit: you link turns with `session_id`.

## End-to-end flow (ASCII)

```text
User → App → /v1/guard/input → (pass|flag|block, session_id) → App → LLM
LLM  → App → /v1/guard/output (session_id) → (pass|flag|block) → App → User
```

## Pipeline layers (input path)

Input evaluation runs a layered pipeline (`defend/api/pipeline/orchestrator.py`):

- **Normalization**: text normalization and cleanup.
- **Intent fast-pass**: short-circuit obviously benign inputs when enabled.
- **Regex heuristics**: pattern-based risk signals.
- **Provider decision**: a semantic decision via `defend`, `claude`, or `openai` (optionally chained).
- **Session accumulation (when `session_id` is present)**: updates a rolling session score and can block once enough risky turns are observed.

Session accumulation implementation details:

- Rolling score uses exponential decay (`alpha = 0.7`) over prior state.
- The gate is `SESSION_BLOCK_THRESHOLD` risky turns (default is `3` via settings).

## Providers and chaining

Providers are the L6 semantic decision engines (`defend/api/providers/`).

Implemented providers:

- `defend`: local Qwen-based classifier (no external API calls). Input-oriented; does not support modules.
- `claude` / `openai`: LLM-backed evaluation; supports modules and is required for output guarding.

Provider chaining is implemented in `defend/api/providers/orchestrator.py`:

- **Confidence escalation** (`primary: defend`, `fallback: claude|openai`): run local classify first; call the LLM provider only when confidence is below `confidence_threshold`.
- **Both-active gate** (`primary: claude|openai`, `fallback: defend`): run `defend` first; hard-block before calling the LLM provider if it blocks.

## Modules

Modules live in `defend/api/modules/` and are direction-scoped:

- Input: `injection`, `pii`, `topic`, `custom`
- Output: `prompt_leak`, `pii_output`, `topic_output`, `custom_output`

LLM providers compose modules by adding their `system_prompt()` fragments to the evaluation prompt. The local `defend` provider ignores modules.

## Sessions: two uses of `session_id`

The codebase uses `session_id` in two distinct places:

- **Pipeline session state** (`defend/api/session.py` + `defend/api/pipeline/session_accumulator.py`): rolling session risk.
- **Input context for output** (`defend/api/guard_session.py`): stores input context for `/v1/guard/output`.

Both are in-memory and per-process. If you run multiple workers, context is not shared unless you add a shared backend.

## Response schema (high level)

Both `/v1/guard/input` and `/v1/guard/output` return a `GuardResult` with:

- `action`: `pass | flag | block | retry_suggested`
- `session_id`
- `decided_by`: `defend | claude | openai`
- `score` / `reason` (nullable)
- `modules_triggered`

See `CONFIGURATION.md` for how provider chains, thresholds, and guard settings are configured.