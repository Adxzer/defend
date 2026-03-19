from __future__ import annotations

from defend_api.config import get_defend_config
from defend_api.routers import guard as guard_router


def test_guard_output_disabled_short_circuits(client, output_provider_stub, monkeypatch) -> None:
    base = get_defend_config()
    cfg = base.model_copy(deep=True)
    cfg.guards.output.enabled = False

    monkeypatch.setattr(guard_router, "get_defend_config", lambda: cfg)

    async def _should_not_be_called(*_args, **_kwargs):  # noqa: ANN001
        raise AssertionError("output provider must not be invoked when output guarding is disabled")

    output_provider_stub.evaluate = _should_not_be_called  # type: ignore[assignment]

    resp = client.post("/v1/guard/output", json={"text": "LLM output"})
    assert resp.status_code == 200
    payload = resp.json()

    assert payload["action"] == "pass"
    assert payload["decided_by"] == "disabled"
    assert payload["context"] == "none"
    assert output_provider_stub.last_text is None

