# Contributing

This repo is small; keep contributions small and testable.

## Workflow

- Branch from `main`.
- Prefer one-purpose branches (feature or fix).
- Open a PR and keep it green.

## Local checks (what CI enforces)

Lint:

```bash
ruff check defend_api defend tests
```

Unit + integration tests:

```bash
pytest -m "unit or integration"
```

API tests (requires a running API):

```bash
set API_BASE_URL=http://127.0.0.1:8000
pytest -m api
```

## Docs changes

Docs are treated as part of the product:

- Don’t claim behavior you didn’t verify in code.
- Prefer “what to do” over “what it is”.
- Keep examples executable (or copy/pasteable) and consistent with `/v1/*` paths.

