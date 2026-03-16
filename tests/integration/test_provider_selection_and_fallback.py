import pytest

from defend_api.config import DefendConfig, GuardsConfig, GuardsInputConfig, GuardsOutputConfig, ProviderConfig
from defend_api.providers.orchestrator import ProviderOrchestrator
from defend_api.schemas import GuardAction, ProviderName


class DummyProvider:
    def __init__(self, name: str, action: str) -> None:
        self.name = name
        self.supports_modules = False
        self._action = action

    async def evaluate(self, text: str, session_id=None, modules=None):
        from defend_api.providers.base import ProviderResult

        return ProviderResult(
            action=self._action,
            provider=self.name,
            score=0.5,
            reason=None,
            modules_triggered=[],
            latency_ms=0,
        )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_orchestrator_primary_defend_only(monkeypatch):
    def fake_get_defend_config():
        return DefendConfig(
            provider=ProviderConfig(primary=ProviderName.DEFEND),
            guards=GuardsConfig(
                input=GuardsInputConfig(),
                output=GuardsOutputConfig(),
            ),
        )

    monkeypatch.setattr("defend_api.providers.orchestrator.get_defend_config", fake_get_defend_config)
    monkeypatch.setattr(
        "defend_api.providers.orchestrator.get_provider",
        lambda name: DummyProvider(name.value, "pass"),
    )

    orchestrator = ProviderOrchestrator()
    result = await orchestrator.evaluate("text")
    assert result.provider == ProviderName.DEFEND.value
    assert result.action == "pass"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_orchestrator_primary_claude_with_defend_fallback(monkeypatch):
    def fake_get_defend_config():
        return DefendConfig(
            provider=ProviderConfig(primary=ProviderName.CLAUDE, fallback=ProviderName.DEFEND),
            guards=GuardsConfig(
                input=GuardsInputConfig(),
                output=GuardsOutputConfig(),
            ),
        )

    monkeypatch.setattr("defend_api.providers.orchestrator.get_defend_config", fake_get_defend_config)

    # First call is defend gate returning pass, second is claude which we force to error via exception.
    from defend_api.providers.base import ProviderResult, ProviderUnavailableError

    class DefendGate(DummyProvider):
        async def evaluate(self, text, session_id=None, modules=None):
            return ProviderResult(
                action=GuardAction.PASS,
                provider="defend",
                score=0.1,
                reason=None,
                modules_triggered=[],
                latency_ms=0,
            )

    class FailingClaude(DummyProvider):
        async def evaluate(self, text, session_id=None, modules=None):
            raise ProviderUnavailableError("down")

    def fake_get_provider(name):
        if name is ProviderName.DEFEND:
            return DefendGate("defend", "pass")
        if name is ProviderName.CLAUDE:
            return FailingClaude("claude", "block")
        raise AssertionError("unexpected provider")

    monkeypatch.setattr("defend_api.providers.orchestrator.get_provider", fake_get_provider)

    orchestrator = ProviderOrchestrator()
    result = await orchestrator.evaluate("text")
    # Because claude fails, the orchestrator should fall back to the defend result.
    assert result.provider == "defend"
    assert result.action is GuardAction.PASS

