import pytest
import httpx


@pytest.mark.integration
@pytest.mark.asyncio
async def test_session_flow_input_then_output_uses_same_session(api_base_url: str):
    async with httpx.AsyncClient(base_url=api_base_url, timeout=5.0) as client:
        in_resp = await client.post(
            "/guard/input",
            json={"text": "Hello, keep this context for later."},
        )
    in_resp.raise_for_status()
    in_data = in_resp.json()
    session_id = in_data["session_id"]

    async with httpx.AsyncClient(base_url=api_base_url, timeout=5.0) as client:
        out_resp = await client.post(
            "/guard/output",
            json={"text": "Using previous context.", "session_id": session_id},
        )
    out_resp.raise_for_status()
    out_data = out_resp.json()

    assert out_data["session_id"] == session_id
    # context field may be 0/1 enum; just assert it's present
    assert "context" in out_data

