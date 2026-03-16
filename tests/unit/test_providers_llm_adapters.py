import json

import pytest

from defend_api.providers.claude.provider import ClaudeProvider
from defend_api.providers.openai.provider import OpenAIProvider
from defend_api.providers.base import ProviderUnavailableError
from defend_api.modules.base import BaseModule


class DummyModule(BaseModule):
    name = "dummy"
    direction = "both"

    def system_prompt(self) -> str:
        return "dummy instructions"


class DummyClaudeContent:
    def __init__(self, text: str) -> None:
        self.text = text


class DummyClaudeResponse:
    def __init__(self, payload: dict) -> None:
        self.content = [DummyClaudeContent(json.dumps(payload))]


class DummyOpenAIMessage:
    def __init__(self, content: str) -> None:
        self.content = content


class DummyOpenAIChoice:
    def __init__(self, message: DummyOpenAIMessage) -> None:
        self.message = message


class DummyOpenAIResponse:
    def __init__(self, payload: dict) -> None:
        self.choices = [DummyOpenAIChoice(DummyOpenAIMessage(json.dumps(payload)))]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_claude_provider_parses_valid_payload(monkeypatch):
    provider = ClaudeProvider()

    payload = {
        "action": "block",
        "score": 0.9,
        "reason": "test reason",
        "modules_triggered": ["dummy"],
    }

    def fake_create(*args, **kwargs):
        return DummyClaudeResponse(payload)

    class DummyClient:
        class messages:
            @staticmethod
            def create(*args, **kwargs):
                return fake_create(*args, **kwargs)

    monkeypatch.setattr("defend_api.providers.claude.provider.Anthropic", lambda: DummyClient())

    result = await provider.evaluate("text", modules=[DummyModule()])
    assert result.action == "block"
    assert result.score == pytest.approx(0.9)
    assert result.reason == "test reason"
    assert result.modules_triggered == ["dummy"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_claude_provider_invalid_json_raises_provider_unavailable(monkeypatch):
    provider = ClaudeProvider()

    class BadContent:
        def __init__(self) -> None:
            self.text = "not-json"

    class BadResponse:
        def __init__(self) -> None:
            self.content = [BadContent()]

    class DummyClient:
        class messages:
            @staticmethod
            def create(*args, **kwargs):
                return BadResponse()

    monkeypatch.setattr("defend_api.providers.claude.provider.Anthropic", lambda: DummyClient())

    with pytest.raises(ProviderUnavailableError):
        await provider.evaluate("text", modules=[DummyModule()])


@pytest.mark.unit
@pytest.mark.asyncio
async def test_openai_provider_parses_valid_payload(monkeypatch):
    provider = OpenAIProvider()

    payload = {
        "action": "flag",
        "score": 0.4,
        "reason": "ok",
        "modules_triggered": ["dummy"],
    }

    class DummyClient:
        class chat:
            class completions:
                @staticmethod
                def create(*args, **kwargs):
                    return DummyOpenAIResponse(payload)

    monkeypatch.setattr("defend_api.providers.openai.provider.OpenAI", lambda: DummyClient())

    result = await provider.evaluate("text", modules=[DummyModule()])
    assert result.action == "flag"
    assert result.score == pytest.approx(0.4)
    assert result.modules_triggered == ["dummy"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_openai_provider_invalid_action_raises(monkeypatch):
    provider = OpenAIProvider()

    payload = {
        "action": "weird",
        "score": 0.1,
        "reason": "bad",
        "modules_triggered": [],
    }

    class DummyClient:
        class chat:
            class completions:
                @staticmethod
                def create(*args, **kwargs):
                    return DummyOpenAIResponse(payload)

    monkeypatch.setattr("defend_api.providers.openai.provider.OpenAI", lambda: DummyClient())

    with pytest.raises(ProviderUnavailableError):
        await provider.evaluate("text")

