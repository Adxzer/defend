from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List

import regex as re
import yaml

from ..logging import get_logger
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
    def __init__(self, patterns_path: Path, block_threshold: float, flag_threshold: float) -> None:
        self._block_threshold = block_threshold
        self._flag_threshold = flag_threshold
        self._patterns: list[dict] = []
        self._compiled: list[tuple[dict, re.Pattern[str]]] = []

        if not patterns_path.exists():
            logger.warning("Regex patterns file not found", extra={"path": str(patterns_path)})
            return

        data = yaml.safe_load(patterns_path.read_text(encoding="utf-8")) or {}
        for entry in data.get("patterns", []):
            pattern = entry.get("regex")
            if not pattern:
                continue
            compiled = re.compile(pattern)
            self._patterns.append(entry)
            self._compiled.append((entry, compiled))

    def run(self, normalized: NormalizedText) -> RegexHeuristicsResult:
        text = normalized.normalized

        total_score = 0.0
        matches: List[RegexMatchResult] = []

        for entry, pattern in self._compiled:
            weight = float(entry.get("weight", 0.0))
            for match in pattern.finditer(text):
                span = match.span()
                snippet = text[max(0, span[0] - 40) : span[1] + 40]
                matches.append(
                    RegexMatchResult(
                        name=entry.get("name", "unnamed"),
                        category=entry.get("category", "unknown"),
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

