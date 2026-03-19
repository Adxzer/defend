from __future__ import annotations

import time
from typing import Optional

from ...models.defend_qwen import get_defend_classifier
from ..base import BaseProvider, ProviderResult


class DefendProvider(BaseProvider):
    name = "defend"
    supports_modules = False

    def __init__(self) -> None:
        # Ensure model can be loaded via the existing helper.
        # We do not trigger loading here to keep startup light;
        # get_defend_classifier() is still responsible for caching.
        self._get_classifier = get_defend_classifier

    async def evaluate(
        self,
        text: str,
        session_id: Optional[str] = None,  # noqa: ARG002
        modules: list | None = None,  # noqa: ARG002
    ) -> ProviderResult:
        start = time.perf_counter()
        classifier = self._get_classifier()
        output = classifier.classify(text)
        latency_ms = int((time.perf_counter() - start) * 1000)

        action = "block" if output.is_injection else "pass"

        return ProviderResult(
            action=action,
            provider=self.name,
            score=output.probability,
            reason=None,
            modules_triggered=[],
            latency_ms=latency_ms,
        )

