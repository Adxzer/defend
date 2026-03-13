from __future__ import annotations

from dataclasses import dataclass

from ..config import get_settings
from ..models.perplexity import PerplexityOutput, get_perplexity_scorer
from .normalization import NormalizedText


@dataclass
class PerplexityResult:
    output: PerplexityOutput
    decision: str  # "BLOCK" | "FLAG" | "CONTINUE"


def run_perplexity_filter(normalized: NormalizedText) -> PerplexityResult:
    settings = get_settings()
    scorer = get_perplexity_scorer()
    output = scorer.score(normalized.normalized)

    if output.value >= settings.PERPLEXITY_BLOCK_THRESHOLD:
        decision = "BLOCK"
    else:
        decision = "CONTINUE"

    return PerplexityResult(output=output, decision=decision)

