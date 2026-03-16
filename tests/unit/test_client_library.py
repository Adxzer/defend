import pytest

from client.client import Client
from client.exceptions import BlockedError, ProviderError
from client.models import GuardResult


class DummyResponse:
    def __init__(self, status_code: int, json_data):
        self.status_code = status_code
        self._json_data = json_data

    def json(self):
        return self._json_data


class DummySyncClient:
    def __init__(self, responses):
        self._responses = responses
        self.posts = []

    def post(self, path, json=None):
        self.posts.append((path, json))
        return self._responses.pop(0)


@pytest.mark.unit
def test_client_input_happy_path(monkeypatch):
    data = {
        "action": "pass",
        "session_id": "s1",
        "decided_by": "defend",
        "direction": "input",
        "score": 0.0,
        "reason": None,
        "modules_triggered": [],
        "context": "none",
        "latency_ms": 0,
    }

    c = Client(api_key="test-key")
    dummy = DummySyncClient([DummyResponse(200, data)])
    monkeypatch.setattr(c, "_client", dummy)

    result = c.input("hello")
    assert isinstance(result, GuardResult)
    assert result.action == "pass"
    assert c._last_session_id == "s1"


@pytest.mark.unit
def test_client_raises_blocked_error_when_configured(monkeypatch):
    data = {
        "action": "block",
        "session_id": "s1",
        "decided_by": "defend",
        "direction": "input",
        "score": 1.0,
        "reason": "blocked",
        "modules_triggered": [],
        "context": "none",
        "latency_ms": 0,
    }

    c = Client(api_key="test-key", raise_on_block=True)
    dummy = DummySyncClient([DummyResponse(200, data)])
    monkeypatch.setattr(c, "_client", dummy)

    with pytest.raises(BlockedError):
        c.input("evil")


@pytest.mark.unit
def test_client_handles_provider_error(monkeypatch):
    c = Client(api_key="test-key")
    dummy = DummySyncClient([DummyResponse(500, {"detail": "boom"})])
    monkeypatch.setattr(c, "_client", dummy)

    with pytest.raises(ProviderError):
        c.input("hello")

