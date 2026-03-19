from __future__ import annotations

from dataclasses import dataclass

import pytest

from defend_api.models.intent import IntentOutput
from defend_api.pipeline.intent_fastpass import run_intent_gate
from defend_api.pipeline.normalization import NormalizedText


@dataclass
class StubOutput:
    label: str
    score: float


class StubIntentClassifier:
    def __init__(self, *, label: str, score: float) -> None:
        self._label = label
        self._score = score

    def classify(self, text: str) -> IntentOutput:  # noqa: ARG002
        return IntentOutput(label=self._label, score=self._score)


def test_intent_fastpass_passes_for_benign_high_score(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "defend_api.pipeline.intent_fastpass.get_intent_classifier",
        lambda: StubIntentClassifier(label="benign", score=0.99),
    )
    res = run_intent_gate(NormalizedText(raw="", normalized="hi"))
    assert res.decision == "PASS"
    assert res.output.label == "benign"
    assert res.output.score == pytest.approx(0.99)


def test_intent_fastpass_continues_for_low_score(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "defend_api.pipeline.intent_fastpass.get_intent_classifier",
        lambda: StubIntentClassifier(label="benign", score=0.1),
    )
    res = run_intent_gate(NormalizedText(raw="", normalized="hi"))
    assert res.decision == "CONTINUE"


def test_intent_fastpass_continues_for_non_benign_label(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "defend_api.pipeline.intent_fastpass.get_intent_classifier",
        lambda: StubIntentClassifier(label="neutral", score=0.99),
    )
    res = run_intent_gate(NormalizedText(raw="", normalized="hi"))
    assert res.decision == "CONTINUE"

