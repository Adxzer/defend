from __future__ import annotations

from dataclasses import dataclass
from typing import List

import regex as re

from ..logging import get_logger
from ..patterns import RegexPattern, get_regex_patterns
from .normalization import NormalizedText


logger = get_logger(__name__)


@dataclass
class RegexMatchResult:
    name: str
    category: str
    weight: float
    span: tuple[int, int] | None
    snippet: str | None


@dataclass
class RegexHeuristicsResult:
    score: float
    decision: str  # "BLOCK" | "FLAG" | "CONTINUE"
    matches: List[RegexMatchResult]


class RegexHeuristics:
    def __init__(self, block_threshold: float, flag_threshold: float) -> None:
        self._block_threshold = block_threshold
        self._flag_threshold = flag_threshold
        self._patterns: List[RegexPattern] = []
        self._compiled: list[tuple[RegexPattern, re.Pattern[str]]] = []

        patterns = get_regex_patterns()
        if not patterns:
            logger.warning("No regex patterns configured for heuristics layer")
            return

        for pattern in patterns:
            compiled = pattern.compile()
            self._patterns.append(pattern)
            self._compiled.append((pattern, compiled))

    def run(self, normalized: NormalizedText) -> RegexHeuristicsResult:
        text = normalized.normalized

        total_score = 0.0
        matches: List[RegexMatchResult] = []

        for entry, pattern in self._compiled:
            weight = float(entry.weight)
            for match in pattern.finditer(text):
                span = match.span()
                snippet = text[max(0, span[0] - 40) : span[1] + 40]
                matches.append(
                    RegexMatchResult(
                        name=entry.name,
                        category=entry.category,
                        weight=weight,
                        span=span,
                        snippet=snippet,
                    )
                )
                total_score += weight

        if total_score >= self._block_threshold:
            decision = "BLOCK"
        elif total_score >= self._flag_threshold:
            decision = "FLAG"
        else:
            decision = "CONTINUE"

        return RegexHeuristicsResult(score=total_score, decision=decision, matches=matches)

