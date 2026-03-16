from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Literal, Optional

from ..modules.base import BaseModule


@dataclass
class ProviderResult:
    action: Literal["pass", "flag", "block"]
    provider: str
    score: Optional[float] = None
    reason: Optional[str] = None
    modules_triggered: list[str] = field(default_factory=list)
    latency_ms: Optional[int] = None


class ProviderUnavailableError(RuntimeError):
    """Raised when an upstream provider is temporarily unavailable."""


class BaseProvider(ABC):
    name: str
    supports_modules: bool = False

    @abstractmethod
    async def evaluate(
        self,
        text: str,
        session_id: Optional[str] = None,
        modules: list[BaseModule] | None = None,
    ) -> ProviderResult:  # pragma: no cover - interface
        ...

    async def health_check(self) -> bool:
        """Override in providers that make external calls."""
        return True


