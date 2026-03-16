import pytest
import httpx

from defend_api.providers.base import ProviderUnavailableError
import defend_api.routers.guard as guard_router


@pytest.mark.api
@pytest.mark.asyncio
async def test_guard_output_provider_unavailable_returns_graceful_error(api_base_url: str, monkeypatch):
    class FailingProvider:
        supports_modules = True

        async def evaluate(self, text, session_id=None, modules=None):
            raise ProviderUnavailableError("upstream down")

    def get_provider_override(name):
        return FailingProvider()

    monkeypatch.setattr(guard_router, "get_provider", get_provider_override)

    async with httpx.AsyncClient(base_url=api_base_url, timeout=5.0) as client:
        resp = await client.post(
            "/guard/output",
            json={"text": "some output text"},
        )
    # This should not crash with a 500; guard_output maps ProviderUnavailableError
    # into a valid GuardResult using on_fail, so 200 is expected.
    assert resp.status_code == 200
    data = resp.json()
    assert data["action"] in {"block", "flag", "retry_suggested"}


@pytest.mark.api
@pytest.mark.asyncio
async def test_guard_input_validation_error_shape(api_base_url: str):
    async with httpx.AsyncClient(base_url=api_base_url, timeout=5.0) as client:
        resp = await client.post("/guard/input", json={"text": 123})
    assert resp.status_code == 422
    data = resp.json()
    assert "detail" in data

