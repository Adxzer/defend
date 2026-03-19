from __future__ import annotations


def test_sessions_delete_then_404(client) -> None:
    session_id = "life-1"

    in_resp = client.post("/v1/guard/input", json={"text": "Hello world", "session_id": session_id})
    assert in_resp.status_code == 200

    del_resp = client.delete(f"/v1/sessions/{session_id}")
    assert del_resp.status_code == 204

    get_resp = client.get(f"/v1/sessions/{session_id}")
    assert get_resp.status_code == 404

