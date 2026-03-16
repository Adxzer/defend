import pytest

from defend_api.providers.defend.provider import DefendProvider
from defend_api.providers.base import ProviderResult


class DummyClassifier:
    def __init__(self, is_injection: bool, probability: float) -> None:
        self.is_injection = is_injection
        self.probability = probability

    def classify(self, text: str) -> "DummyClassifier":  # type: ignore[override]
        return self


@pytest.mark.unit
@pytest.mark.asyncio
async def test_defend_provider_pass_action_for_non_injection():
    provider = DefendProvider()
    provider._get_classifier = lambda: DummyClassifier(False, 0.2)  # type: ignore[assignment]

    result = await provider.evaluate("benign text")
    assert isinstance(result, ProviderResult)
    assert result.action == "pass"
    assert result.provider == "defend"
    assert result.score == pytest.approx(0.2)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_defend_provider_block_action_for_injection():
    provider = DefendProvider()
    provider._get_classifier = lambda: DummyClassifier(True, 0.9)  # type: ignore[assignment]

    result = await provider.evaluate("malicious text")
    assert result.action == "block"
    assert result.score == pytest.approx(0.9)

