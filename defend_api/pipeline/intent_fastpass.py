from __future__ import annotations

from dataclasses import dataclass

from ..config import get_settings
from ..models.intent import IntentOutput, get_intent_classifier
from .normalization import NormalizedText


@dataclass
class IntentGateResult:
    output: IntentOutput
    decision: str  # "PASS" or "CONTINUE"


def run_intent_gate(normalized: NormalizedText) -> IntentGateResult:
    settings = get_settings()
    if not bool(getattr(settings, "INTENT_FASTPASS_ENABLED", True)):
        classifier = get_intent_classifier()
        output = classifier.classify(normalized.normalized)
        return IntentGateResult(output=output, decision="CONTINUE")
    classifier = get_intent_classifier()
    output = classifier.classify(normalized.normalized)

    if output.label == "benign" and output.score >= settings.INTENT_FASTPASS_THRESHOLD:
        decision = "PASS"
    else:
        decision = "CONTINUE"

    return IntentGateResult(output=output, decision=decision)

