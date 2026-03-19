from __future__ import annotations


def test_ready_endpoint(client) -> None:
    resp = client.get("/v1/ready")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ready"}

