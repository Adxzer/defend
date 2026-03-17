from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Literal


class BaseModule(ABC):
    """Abstract base for all guard modules used by LLM providers."""

    name: str
    description: str
    direction: Literal["input", "output", "both"] = "input"

    @abstractmethod
    def system_prompt(self) -> str:  # pragma: no cover - interface
        """Return the prompt fragment for this module."""
        ...

