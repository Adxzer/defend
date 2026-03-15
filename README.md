![License](https://img.shields.io/badge/license-Apache--2.0-blue)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![Languages](https://img.shields.io/badge/languages-30%2B-green)
![Docker](https://img.shields.io/badge/docker-ready-blue)

## Defend API Microservice

Defend API is a standalone, open-source HTTP microservice implementing a six-layer safety pipeline:

- **L1**: Text normalization
- **L2**: Intent fast-pass using a lightweight embedding model
- **L3**: Regex and heuristic scoring from a YAML pattern library
- **L4**: Perplexity-based filter 
- **L5**: Multi-turn session accumulation backed by Redis
- **L6**: Final semantic classifier using the `Adaxer/defend` checkpoint (trained on [Qwen2.5-0.5B-Instruct](https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct))

The goal is a reusable guardrail service that can sit in front of any LLM stack.

### Why Defend?

LLMs are vulnerable to prompt injection and jailbreaking in many languages, but most guardrails are English-only. Defend uses a multilingual pipeline (including a classifier trained on [Qwen2.5-0.5B-Instruct](https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct)) so you can protect your stack across the languages your users speak.

### Supported Languages

The semantic classifier is trained on [Qwen2.5-0.5B-Instruct](https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct), which supports **29+ languages**, including Chinese, English, French, Spanish, Portuguese, German, Italian, Russian, Japanese, Korean, Vietnamese, Thai, Arabic, and more.

### Quick start

```bash
pip install -r requirements.txt
uvicorn defend_api.main:app --reload
```

Then call:

```bash
curl -X POST "http://localhost:8000/classify" \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello world", "session_id": "demo"}'
```

The service returns a JSON object containing `is_injection`, a `final_action`, and per-layer diagnostics under `layers`.

### Model loading & caching

By default, Defend API downloads its models from Hugging Face on first use and relies on the standard Transformers/SentenceTransformer libraries:

- Intent (L2) uses `sentence-transformers/all-MiniLM-L6-v2`.
- Perplexity (L4) uses a small GPT‑2 model (e.g. `gpt2`).
- Defend (L6) uses the `Adaxer/defend` classifier checkpoint.

```bash
INTENT_MODEL_ID=sentence-transformers/all-MiniLM-L6-v2
PERPLEXITY_MODEL_ID=gpt2
DEFEND_MODEL_ID=Adaxer/defend
```

On startup (or on first request), the service will:

- Download the required models from Hugging Face into the standard local cache.
- Fail readiness (`/ready`) and classification (`/classify`) if any mandatory model or Redis is unavailable.

### API surface

- `POST /classify` – main classification endpoint.
- `GET /health` – lightweight health check.
- `GET /ready` – readiness hook for container orchestration.
- `GET /metrics` – Prometheus metrics via `prometheus-fastapi-instrumentator`.
- `GET /models`, `POST /invoke` – optional compatibility endpoints.

See `ARCHITECTURE.md` for more detail on the design and pipeline flow.

