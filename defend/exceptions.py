from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional


class DefendError(Exception):
    """
    Base error for the Defend Python SDK.
    """

    def __init__(self, message: str, *, details: Any | None = None) -> None:
        super().__init__(message)
        self.details = details


class DefendConnectionError(DefendError):
    """
    Raised when the Defend server cannot be reached.
    """


class DefendBlockedError(DefendError):
    """
    Raised when a guard call blocks and the client is configured to raise.
    """

    def __init__(self, message: str, *, result: Any) -> None:
        super().__init__(message, details=result)
        self.result = result


@dataclass(frozen=True)
class DefendHTTPError(DefendError):
    """
    Raised for non-2xx HTTP responses from the Defend API.
    """

    status_code: int
    payload: Any | None = None
    headers: Optional[Mapping[str, str]] = None

    def __str__(self) -> str:  # pragma: no cover - trivial
        base = super().__str__()
        return f"{base} (status_code={self.status_code})"

