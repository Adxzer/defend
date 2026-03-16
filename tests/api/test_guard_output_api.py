import pytest
import httpx


async def _create_session(api_base_url: str) -> str:
    async with httpx.AsyncClient(base_url=api_base_url, timeout=5.0) as client:
        resp = await client.post(
            "/guard/input",
            json={"text": "Hello, please help me with a simple question."},
        )
    resp.raise_for_status()
    data = resp.json()
    return data["session_id"]


@pytest.mark.api
@pytest.mark.asyncio
async def test_guard_output_happy_path_with_session(api_base_url: str):
    session_id = await _create_session(api_base_url)

    async with httpx.AsyncClient(base_url=api_base_url, timeout=5.0) as client:
        resp = await client.post(
            "/guard/output",
            json={
                "text": "Here is a harmless model response.",
                "session_id": session_id,
            },
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["direction"] == "output"
    assert data["session_id"]
    # action will depend on configuration; just assert it is a valid value
    assert data["action"] in {"pass", "flag", "block", "retry_suggested"}


@pytest.mark.api
@pytest.mark.asyncio
async def test_guard_output_missing_session_id_allowed(api_base_url: str):
    async with httpx.AsyncClient(base_url=api_base_url, timeout=5.0) as client:
        resp = await client.post(
            "/guard/output",
            json={"text": "Response without a session id."},
        )
    # Depending on config, this should still be processed; at minimum it should not 5xx
    assert resp.status_code in {200, 400}

