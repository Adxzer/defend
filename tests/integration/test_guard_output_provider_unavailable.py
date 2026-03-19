from __future__ import annotations

from defend_api.config import get_defend_config
from defend_api.providers.base import ProviderUnavailableError
from defend_api.routers import guard as guard_router


def test_guard_output_provider_unavailable_uses_on_fail(
    client,
    output_provider_stub,
    monkeypatch,
) -> None:
    base = get_defend_config()
    cfg = base.model_copy(deep=True)
    cfg.guards.output.enabled = True

    monkeypatch.setattr(guard_router, "get_defend_config", lambda: cfg)

    async def _unavailable(*_args, **_kwargs):  # noqa: ANN001
        raise ProviderUnavailableError("provider is down")

    output_provider_stub.evaluate = _unavailable  # type: ignore[assignment]

    resp = client.post("/v1/guard/output", json={"text": "LLM output"})
    assert resp.status_code == 200
    payload = resp.json()

    assert payload["context"] == "none"
    assert payload["decided_by"] == cfg.guards.output.provider.value
    assert payload["action"] == cfg.guards.output.on_fail.value
    assert "provider is down" in (payload.get("reason") or "")

