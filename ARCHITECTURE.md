## Architecture overview

DEFEND is a FastAPI microservice that exposes a small HTTP surface and wraps a six-layer safety pipeline:

- **L1 – Normalization**: text cleaning, canonicalisation.
- **L2 – Intent fast-pass**: lightweight embedding model that can short-circuit obvious benign input.
- **L3 – Regex heuristics**: pattern-based scoring from `config/patterns.yaml`.
- **L4 – Perplexity filter**: language-model perplexity to spot obviously machine-generated / copy-pasted payloads.
- **L5 – Session accumulator**: Redis-backed rolling risk score across turns.
- **L6 – Provider layer**: pluggable providers (`defend`, `claude`, `openai`) that make the final decision.

The HTTP layer is intentionally thin; all logic lives in `defend_api.pipeline`, `defend_api.providers`, `defend_api.modules`, and `defend_api.guard_session`.

---

## Six-layer pipeline

The main pipeline entry point is `defend_api.pipeline.orchestrator.run_pipeline(text, session_id)`. It:

1. Normalizes input (`pipeline.normalization`) and emits `NormalizationDiagnostics`.
2. Runs the intent fast-pass (`pipeline.intent_fastpass`); obvious benign inputs can short-circuit to `FinalAction.PASS`.
3. Applies regex heuristics (`pipeline.regex_heuristics`) using `config/patterns.yaml`.
4. Applies a perplexity filter (`pipeline.perplexity_filter`) using a GPT‑2–style LM.
5. Updates the session accumulator (`pipeline.session_accumulator`) in Redis when `session_id` is present.
6. Delegates the final decision to the provider orchestrator (L6).

The orchestrator returns an `OrchestratorResult` containing:

- `is_injection: bool`
- `final_action: FinalAction`
- `layers: LayerDiagnostics` (L1–L5 + defend diagnostics)
- provider metadata used to fill response schema v2: `decided_by`, `score`, `reason`, `modules_triggered`, `latency_ms`.

L1–L5 are always run; they are not configurable per request.

---

## Provider system (L6)

### BaseProvider and registry

Providers live under `defend_api/providers/` and are discovered automatically.

- `defend_api.providers.base.BaseProvider` is an abstract class:
  - Attributes: `name: str`, `supports_modules: bool`.
  - Method:
    - `async evaluate(text: str, session_id: Optional[str] = None, modules: list[BaseModule] | None = None) -> ProviderResult`
- `ProviderResult` carries:
  - `action: "pass" | "flag" | "block"`
  - `provider: str`
  - optional `score`, `reason`, `modules_triggered`, `latency_ms`.

The registry in `defend_api/providers/__init__.py`:

- Scans subpackages (e.g. `providers/defend`, `providers/claude`, `providers/openai`) and imports `<name>.provider`.
- Instantiates any `BaseProvider` subclass and registers it by `instance.name`.
- Exposes `get_provider(name)` and `get_all_providers()`.

Adding a new provider is “drop-in”: create `providers/<name>/provider.py` with a `BaseProvider` subclass; no central registry edits are needed.

### Orchestrator and gate logic

`defend_api.providers.orchestrator.ProviderOrchestrator` owns provider selection:

- Reads `provider` (primary + optional fallback) from `defend.config.yaml` via `get_defend_config()`.
- **Single-provider mode**:
  - Calls the configured provider (`defend`, `claude`, or `openai`).
  - If `supports_modules` is true, passes the currently active modules (input-side evaluations use only input/both modules; output-side will use output/both).
- **Both-active mode** (LLM + defend):
  - When `primary` is an LLM (`claude` or `openai`) and `fallback: "defend"`:
    - Run `defend` first as a gate.
    - If defend says `block`, stop; no LLM call.
    - If defend says `pass`, call the LLM provider with modules.
    - On LLM failure (`ProviderUnavailableError`), fall back to defend’s result.

This gate logic is used for input evaluation. Output evaluation uses only an LLM provider; using `defend` as an output provider is treated as a config error.

### Defend provider specifics

`providers/defend/provider.py` wraps the original `Adaxer/defend` classifier:

- Loads the `DefendQwenClassifier` (`defend_api.models.defend_qwen`) via `get_defend_classifier()`.
- Produces a binary decision (`block` or `pass`) based on the model’s injection probability.
- Sets `supports_modules = False`.
- Never participates in output evaluation; only input.

In responses, `decided_by == "defend"` implies `score` and `reason` are `null`/`None`.

---

## Module system

Modules live under `defend_api/modules/` and are discovered similarly to providers.

### BaseModule and registry

`defend_api.modules.base.BaseModule` defines:

- `name: str`
- `description: str`
- `direction: Literal["input", "output", "both"] = "input"`
- `system_prompt() -> str` — prompt fragment for the LLM.

The registry in `defend_api/modules/__init__.py`:

- Discovers modules from `modules/*/module.py` and `modules/*/output_module.py`.
- Instantiates `BaseModule` subclasses and registers them by `name`.
- Exposes:
  - `get_module(name)`
  - `get_active_modules()` (all)
  - `get_modules_for_input()` — `direction in {"input","both"}`.
  - `get_modules_for_output()` — `direction in {"output","both"}`.

### Built-in modules

Input-only:

- `InjectionGuardModule` (`modules/injection/module.py`) — injection and override attempts.
- `PIIGuardModule` (`modules/pii/module.py`) — PII submission in input.
- `TopicGuardModule` (`modules/topic/module.py`) — off-topic input relative to configured topics.
- `CustomModule` (`modules/custom/module.py`) — raw input-side prompt.

Output-only:

- `PIIOutputModule` (`modules/pii/output_module.py`) — PII leakage in responses.
- `TopicOutputModule` (`modules/topic/output_module.py`) — response scope drift.
- `PromptLeakModule` (`modules/prompt_leak/output_module.py`) — system prompt / internal instruction exposure.
- `CustomOutputModule` (`modules/custom/output_module.py`) — raw output-side prompt.

Modules compose by concatenating their `system_prompt()` fragments into the LLM provider’s evaluation prompt.

---

## Guard session store

Guard endpoints add an extra session layer on top of the pipeline.

`defend_api.guard_session.GuardSessionStore`:

- Uses Redis (same URL as the session accumulator).
- Stores input-side context under key `guard:session:{session_id}` with a TTL (`guards.session_ttl_seconds`, default ~300s).
- Context shape: `{"text": str, "provider": str, "score": float|None}`.
- Provides:
  - `save_input_context(session_id, context)`
  - `get_input_context(session_id) -> dict | None`

The flow:

- `POST /guard/input`:
  - Runs the full pipeline + provider layer for input.
  - Generates or accepts `session_id`.
  - Saves input context to Redis.
  - Returns a `GuardResult` with `direction: "input"` and the `session_id`.
- `POST /guard/output`:
  - Optionally looks up input context via `session_id`.
  - Runs output evaluation using an LLM provider and output modules.
  - Returns a `GuardResult` with `direction: "output"` and `context: "session"` when input context was used, otherwise `"none"`.

Without `session_id`, output evaluation is stateless; this still works but accuracy is lower, and `context` is reported as `"none"`.

---

## Response schemas

### `/guard/input` and `/guard/output`

`POST /guard/input` and `POST /guard/output` use:

- Requests: `GuardInputRequest` / `GuardOutputRequest`:
  - `text: str`
  - `session_id: Optional[str]`
  - `metadata: Optional[dict]`
- Response: `GuardResult`:
  - `action: "pass" | "flag" | "block" | "retry_suggested"`
  - `session_id: str`
  - `decided_by: str`
  - `direction: "input" | "output"`
  - `score: Optional[float]`
  - `reason: Optional[str]`
  - `modules_triggered: list[str]`
  - `context: "session" | "none"`
  - `latency_ms: int`

`GuardResult` also provides:

- `blocked` property (`True` when `action == "block"`).
- `error_response(message: Optional[str]) -> dict` for returning a simple error payload to callers.

These models are implemented in `defend_api.schemas` and mirrored in the Python client package.

---

## What the defend provider can and cannot do

- **What it does**:
  - Binary classification of input as safe vs injection-like.
  - Runs as a provider in L6, optionally in front of an LLM provider (both-active mode) for input guarding.
  - Provides `DefendDiagnostics` with `is_injection` and a probability used internally.

- **What it does not do**:
  - It is **not** used for output evaluation; using it as an output provider is a config error.
  - It does not support modules (`supports_modules = False`).
  - Its probability is not a calibrated score; the service treats it as binary and leaves `score` as `None` when `decided_by == "defend"` in public responses.

For full config details, see `defend.config.yaml`, which documents all provider, module, and guard options in comments.***
