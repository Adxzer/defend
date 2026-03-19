from __future__ import annotations


def test_guard_output_without_session_sets_none_context(client, output_provider_stub) -> None:
    resp = client.post("/v1/guard/output", json={"text": "LLM output"})
    assert resp.status_code == 200
    payload = resp.json()

    assert payload["context"] == "none"
    assert output_provider_stub.last_session_id is None

