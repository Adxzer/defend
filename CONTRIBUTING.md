# Contributing

## Git workflow

- The `main` branch should always be green and deployable.
- All changes should be developed on short-lived feature branches created from `main`, for example:
  - `feature/add-api-tests`
  - `fix/guard-session-bug`
- Open a pull request from your feature branch into `main`.
- Wait for CI to complete and ensure all required checks are green before merging:
  - `lint`
  - `tests`
  - `api-tests`

## Running checks locally

- Lint:

```bash
ruff check defend_api client tests
```

- Unit and integration tests:

```bash
pytest -m "unit or integration"
```

- API tests (with the API running locally):

```bash
export API_BASE_URL="http://127.0.0.1:8000"
pytest -m api
```

GitHub branch protection rules should be configured so that `lint`, `tests`, and `api-tests` must pass before merging into `main`.

