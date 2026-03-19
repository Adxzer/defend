from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Set

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
    def __init__(
        self,
        block_threshold: float,
        flag_threshold: float,
        *,
        block_categories: List[str] | None = None,
        flag_min_matches: int = 2,
    ) -> None:
        self._block_threshold = block_threshold
        self._flag_threshold = flag_threshold
        self._block_categories: Set[str] = {c for c in (block_categories or []) if isinstance(c, str) and c.strip()}
        self._flag_min_matches = max(1, int(flag_min_matches))
        self._patterns: List[RegexPattern] = []
        self._compiled: list[tuple[RegexPattern, re.Pattern[str]]] = []
        self._max_matches_per_pattern = 3

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
        match_counts_by_category: Dict[str, int] = {}

        for entry, pattern in self._compiled:
            weight = float(entry.weight)
            matched_count = 0
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
                matched_count += 1
                match_counts_by_category[entry.category] = match_counts_by_category.get(entry.category, 0) + 1
                if matched_count >= self._max_matches_per_pattern:
                    break

        if self._block_categories and any(match_counts_by_category.get(c, 0) > 0 for c in self._block_categories):
            decision = "BLOCK"
        elif total_score >= self._block_threshold:
            decision = "BLOCK"
        elif total_score >= self._flag_threshold:
            decision = "FLAG"
        elif total_score > 0.0 and len(matches) >= self._flag_min_matches:
            decision = "FLAG"
        else:
            decision = "CONTINUE"

        return RegexHeuristicsResult(score=total_score, decision=decision, matches=matches)

