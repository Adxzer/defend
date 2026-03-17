from __future__ import annotations

import time
from dataclasses import dataclass
from functools import lru_cache
from typing import Dict, Optional, Protocol

from .config import get_settings


@dataclass
class SessionState:
    session_id: str
    history: list[float]
    peak_score: float
    rolling_score: float
    risky_turns: int


class SessionBackend(Protocol):
    async def get(self, session_id: str) -> Optional[SessionState]:
        ...

    async def update(self, session: SessionState) -> None:
        ...

    async def delete(self, session_id: str) -> None:
        ...


# Backing store for the default in-memory backend.
# This is intentionally module-level so unit tests and local debugging can
# inspect/clear state deterministically.
_IN_MEMORY_SESSIONS: Dict[str, SessionState] = {}
_IN_MEMORY_EXPIRES_AT: Dict[str, float] = {}


class InMemoryBackend:
    """Default session backend (no dependencies, per-process, TTL-based)."""

    def __init__(self, ttl_seconds: int) -> None:
        self._ttl_seconds = ttl_seconds

    def _now(self) -> float:
        return time.time()

    def _cleanup_expired(self) -> None:
        now = self._now()
        expired = [sid for sid, exp in _IN_MEMORY_EXPIRES_AT.items() if exp <= now]
        for sid in expired:
            _IN_MEMORY_SESSIONS.pop(sid, None)
            _IN_MEMORY_EXPIRES_AT.pop(sid, None)

    async def get(self, session_id: str) -> Optional[SessionState]:
        self._cleanup_expired()
        state = _IN_MEMORY_SESSIONS.get(session_id)
        if state is None:
            return None
        expires_at = _IN_MEMORY_EXPIRES_AT.get(session_id, 0.0)
        if expires_at <= self._now():
            _IN_MEMORY_SESSIONS.pop(session_id, None)
            _IN_MEMORY_EXPIRES_AT.pop(session_id, None)
            return None
        return state

    async def update(self, session: SessionState) -> None:
        self._cleanup_expired()
        expires_at = self._now() + self._ttl_seconds
        _IN_MEMORY_SESSIONS[session.session_id] = session
        _IN_MEMORY_EXPIRES_AT[session.session_id] = expires_at

    async def delete(self, session_id: str) -> None:
        _IN_MEMORY_SESSIONS.pop(session_id, None)
        _IN_MEMORY_EXPIRES_AT.pop(session_id, None)


@lru_cache(maxsize=1)
def get_session_backend() -> SessionBackend:
    settings = get_settings()

    ttl_seconds = getattr(settings, "SESSION_TTL_SECONDS", 1800)
    return InMemoryBackend(ttl_seconds=int(ttl_seconds))

