from __future__ import annotations

from typing import Any, Optional


class DefendError(Exception):
    """Base error type for defend-py."""

    def __init__(self, message: str, response: Optional[Any] = None) -> None:
        super().__init__(message)
        self.response = response


class BlockedError(DefendError):
    """Raised when raise_on_block=True and a guard call blocks."""


class ConfigError(DefendError):
    """Raised when client configuration is invalid."""


class ProviderError(DefendError):
    """Raised when the server returns a provider-related error."""

