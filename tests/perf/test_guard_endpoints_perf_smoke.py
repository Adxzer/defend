import time

import pytest
import httpx


@pytest.mark.perf
@pytest.mark.asyncio
async def test_guard_endpoints_perf_smoke(api_base_url: str):
    async with httpx.AsyncClient(base_url=api_base_url, timeout=10.0) as client:
        start = time.perf_counter()

        # Small batch of input + output calls to exercise basic latency.
        for _ in range(10):
            in_resp = await client.post("/guard/input", json={"text": "perf smoke test"})
            in_resp.raise_for_status()
            session_id = in_resp.json()["session_id"]

            out_resp = await client.post(
                "/guard/output",
                json={"text": "perf smoke test response", "session_id": session_id},
            )
            out_resp.raise_for_status()

        elapsed = time.perf_counter() - start
        avg_per_call_ms = (elapsed / 20) * 1000.0

        # Loose bound suitable for CI; adjust if needed.
        assert avg_per_call_ms < 500

