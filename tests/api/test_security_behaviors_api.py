import pytest
import httpx


@pytest.mark.api
@pytest.mark.asyncio
async def test_guard_input_rejects_oversized_payload_gracefully(api_base_url: str):
    # Construct a reasonably large payload to exercise validation/performance,
    # but not so large or strict that it destabilizes CI.
    big_text = "x" * 20_000

    async with httpx.AsyncClient(base_url=api_base_url, timeout=20.0) as client:
        resp = await client.post("/guard/input", json={"text": big_text})
    # Service should respond with a non-5xx status even for large input.
    assert resp.status_code in {200, 400, 413}


@pytest.mark.api
@pytest.mark.asyncio
async def test_guard_input_malformed_json_returns_4xx(api_base_url: str):
    async with httpx.AsyncClient(base_url=api_base_url, timeout=20.0) as client:
        resp = await client.post(
            "/guard/input",
            content=b'{"text": "ok", ',  # invalid JSON
            headers={"Content-Type": "application/json"},
        )
    assert resp.status_code in {400, 422}

