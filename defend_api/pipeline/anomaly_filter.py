from __future__ import annotations

from dataclasses import dataclass

from .anomaly_scorer import AnomalyResult, get_anomaly_scorer
from .normalization import NormalizedText


@dataclass
class AnomalyFilterResult:
    output: AnomalyResult
    decision: str  # "WARMUP" | "FLAG" | "CONTINUE"
    samples_seen: int


def run_anomaly_filter(normalized: NormalizedText) -> AnomalyFilterResult:
    scorer = get_anomaly_scorer()
    output = scorer.score(normalized.normalized)
    samples_seen = scorer.get_samples_seen()

    if output.get("status") == "warmup":
        decision = "WARMUP"
    else:
        decision = "FLAG" if bool(output["flagged"]) else "CONTINUE"

    return AnomalyFilterResult(output=output, decision=decision, samples_seen=samples_seen)

