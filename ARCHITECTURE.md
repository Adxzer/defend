## Defend API Architecture

The Defend API microservice consists of:

- A FastAPI application that exposes `/classify`, `/health`, `/ready`, `/metrics`, and optional compatibility endpoints.
- A six-layer safety pipeline implemented as importable Python modules under `defend_api.pipeline`.
- Thin model wrappers around Hugging Face Transformers / SentenceTransformer models under `defend_api.models`.
- A configuration system based on `pydantic-settings` in `defend_api.config`.

The HTTP layer is intentionally thin; the main value lives in the pipeline modules, which can be embedded directly into other Python services.

### Layer overview

- `pipeline.normalization` – implements `normalize_text` and the `NormalizedText` dataclass.
- `pipeline.intent_fastpass` – wraps the `IntentClassifier` model and decides whether to short-circuit as `PASS`.
- `pipeline.regex_heuristics` – loads patterns from `config/patterns.yaml` and produces a weighted score and match details.
- `pipeline.perplexity_filter` – calls a `PerplexityScorer` backed by a GPT‑2 language model.
- `pipeline.session_accumulator` – stores rolling scores in Redis to detect slow-burn attacks.
- `pipeline.orchestrator` – coordinates all layers and returns a structured result for the API.

All public interfaces are typed and designed for extension and experimentation by the community.

### Model loading

- All model configuration lives in `defend_api.config.Settings`.
- Intent (L2) uses `INTENT_MODEL_ID` (default `sentence-transformers/all-MiniLM-L6-v2`) and the SentenceTransformer library.
- Perplexity (L4) and Defend (L6) are loaded from Hugging Face via standard Transformers model classes using `PERPLEXITY_MODEL_ID` and `DEFEND_MODEL_ID`.

The `/ready` endpoint verifies that all mandatory models can be loaded and that Redis is reachable before the service is considered ready.

