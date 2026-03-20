# Contributing to Defend

Thanks for your interest in improving `defend`! Contributions are welcome via pull requests.

## How to contribute

1. Create a branch off `main`.
2. Make your changes.
3. Add/adjust tests and update behavior docs as needed.
4. Open a PR against `main` and fill out the PR template sections.

## Development setup

Defend requires Python `>=3.12`.

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -e .
```

## Run the checks

```bash
ruff check defend_api defend
python -m compileall defend_api defend
pytest -q
```

## PR expectations

- CI must pass (`lint`, `typecheck`, `test`, and `PR Template Check`).
- Keep PRs focused; if you add a new module or guard, include minimal coverage for expected behavior.
- Avoid committing secrets (API keys, tokens, etc.).

## Release process (maintainer only)

Publishing to PyPI and Docker is done from `.github/workflows/release.yml` via a manual `workflow_dispatch` run on the `main` branch.

Contributors should not rely on `v*` tags for publishing—those tag-based publish triggers are disabled for safety.

## Security

See [`SECURITY.md`](SECURITY.md) for responsible disclosure guidance.

