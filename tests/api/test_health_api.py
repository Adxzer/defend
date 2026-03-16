import pytest
import httpx


@pytest.mark.api
@pytest.mark.asyncio
async def test_health_endpoint_ok(api_base_url: str):
    async with httpx.AsyncClient(base_url=api_base_url, timeout=5.0) as client:
        resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    # response schema is intentionally loose; just check it's a dict
    assert isinstance(data, dict)

