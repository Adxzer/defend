# Architecture

Your LLM trusts everything. DEFEND doesn't.

DEFEND is a FastAPI microservice that wraps a six-layer safety pipeline and exposes a session-scoped input/output guard API. Every request is evaluated before it reaches your LLM. Every response is evaluated before it reaches your user. Your LLM call is never touched.

---

## The pipeline

All requests pass through L1–L5 unconditionally, then reach the provider layer (L6) for the final decision.

| Layer | Name | What it does |
|---|---|---|
| L1 | Normalization | Text cleaning, Unicode canonicalization, homoglyph substitution |
| L2 | Intent fast-pass | Lightweight embedding model — obvious benign inputs exit early |
| L3 | Regex heuristics | Pattern scoring from `config/patterns.yaml` |
| L4 | Perplexity filter | GPT-2-style LM flags anomalous or machine-generated payloads |
| L5 | Session accumulator | Redis-backed rolling risk score across conversation turns |
| L6 | Provider layer | Final semantic decision — defend, claude, or openai |

Entry point: `defend_api.pipeline.orchestrator.run_pipeline(text, session_id)`. Returns an `OrchestratorResult` with `is_injection`, `final_action`, per-layer `LayerDiagnostics`, and provider metadata.

---

## Providers

Providers live in `defend_api/providers/`. Drop a folder in with a `BaseProvider` subclass and it's discovered automatically on startup — no registry edits.
```
providers/
  base.py          # BaseProvider, ProviderResult
  __init__.py      # auto-discovery + get_provider()
  orchestrator.py  # gate logic
  defend/
  claude/
  openai/
```

### BaseProvider interface
```python
class BaseProvider(ABC):
    name: str
    supports_modules: bool = False

    async def evaluate(
        self,
        text: str,
        session_id: Optional[str] = None,
        modules: list[BaseModule] | None = None,
    ) -> ProviderResult: ...
```

`ProviderResult` carries `action` (`pass` / `flag` / `block`), `provider`, and optional `score`, `reason`, `modules_triggered`, `latency_ms`.

### Provider options

**`defend`** — wraps the `Adaxer/defend` Qwen2.5 classifier. Binary output, no modules, input-only. Fast, free, no external calls. `score` and `reason` are always `null` in responses.

**`claude`** — Anthropic API with structured JSON output enforced via tool use. Supports all input and output modules. Required for output guarding.

**`openai`** — OpenAI API with `response_format: json_object`. Same module model as Claude.

### Gate logic (both-active mode)

When `primary` is an LLM provider and `fallback: defend` is set:

1. `defend` runs first on every input request.
2. If defend says `block` → stop. LLM provider is never called.
3. If defend says `pass` → LLM provider runs with active modules.
4. If the LLM call fails → fall back to defend's result, log the failure.

Output evaluation always uses an LLM provider. Setting `defend` as an output provider is a config error caught on startup.

---

## Modules

Modules live in `defend_api/modules/`. Same drop-in discovery pattern as providers.
```
modules/
  base.py                     # BaseModule
  __init__.py                 # auto-discovery, direction-aware getters
  injection/module.py
  pii/module.py
  pii/output_module.py
  topic/module.py
  topic/output_module.py
  prompt_leak/output_module.py
  custom/module.py
  custom/output_module.py
```

### BaseModule interface
```python
class BaseModule(ABC):
    name: str
    description: str
    direction: Literal["input", "output", "both"] = "input"

    def system_prompt(self) -> str: ...
```

The registry exposes `get_modules_for_input()` and `get_modules_for_output()` — filtering by `direction` — so the orchestrator always passes the right modules to the right evaluation.

### Built-in modules

| Module | Direction | Detects |
|---|---|---|
| `injection` | input | Overrides, persona hijacking, jailbreaks, social engineering |
| `pii` | input | PII submitted in user requests |
| `pii_output` | output | PII leaking in model responses |
| `topic` | input | Requests outside configured allowed topics |
| `topic_output` | output | Responses drifting outside configured allowed topics |
| `prompt_leak` | output | System prompt or internal instruction exposure |
| `custom` | input | User-defined detection in plain language |
| `custom_output` | output | User-defined detection in plain language |

Modules compose additively — each contributes a `system_prompt()` fragment appended to the LLM evaluation prompt.

---

## Guard sessions

`/guard/input` and `/guard/output` share context through a Redis-backed session store (`defend_api.guard_session.GuardSessionStore`).

**On `/guard/input`:**
- Runs the full L1–L6 pipeline for input evaluation.
- Saves `{ text, provider, score }` to Redis under `guard:session:{session_id}` with a configurable TTL (default 300s).
- Returns a `GuardResult` with `direction: "input"` and the `session_id`.

**On `/guard/output`:**
- Looks up input context from Redis using `session_id` (if provided).
- Runs output evaluation using an LLM provider and output modules.
- Returns a `GuardResult` with `direction: "output"` and `context: "session"` when input context was available, `"none"` when not.

Without a `session_id`, output evaluation is stateless — it still works, but the LLM provider has no knowledge of what was asked.

---

## Response schemas

### `/guard/input` and `/guard/output`
```python
class GuardResult(BaseModel):
    action:            Literal["pass", "flag", "block", "retry_suggested"]
    session_id:        str
    decided_by:        str                    # "defend" | "claude" | "openai"
    direction:         Literal["input", "output"]
    score:             Optional[float]        # null when decided_by == "defend"
    reason:            Optional[str]          # null when decided_by == "defend"
    modules_triggered: list[str]
    context:           Literal["session", "none"]
    latency_ms:        int

    @property
    def blocked(self) -> bool: ...

    def error_response(self, message: str = None) -> dict: ...
```

---

## Adding a provider or module

**New provider:**
1. Create `defend_api/providers/<name>/provider.py`.
2. Define a class inheriting `BaseProvider`.
3. Restart. The registry discovers it automatically.

**New module:**
1. Create `defend_api/modules/<name>/module.py` (input) or `output_module.py` (output).
2. Define a class inheriting `BaseModule`. Set `direction` correctly.
3. Restart. The registry discovers it automatically.

No other files change in either case.

---

For config reference, see `defend.config.yaml`. Every option is documented inline.