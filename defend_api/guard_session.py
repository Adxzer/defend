from __future__ import annotations

from typing import Any, Dict, Optional, Tuple
import time

from .config import get_defend_config


# session_id -> (context_dict, expires_at)
_GUARD_SESSIONS: Dict[str, Tuple[Dict[str, Any], float]] = {}
_guard_store: Optional["GuardSessionStore"] = None


class GuardSessionStore:
    def __init__(self, ttl_seconds: int) -> None:
        self._ttl = ttl_seconds

    async def save_input_context(self, session_id: str, context: Dict[str, Any]) -> None:
        now = time.time()
        expires_at = now + self._ttl
        _GUARD_SESSIONS[session_id] = (context, expires_at)

    async def get_input_context(self, session_id: str) -> Optional[Dict[str, Any]]:
        now = time.time()
        entry = _GUARD_SESSIONS.get(session_id)
        if entry is None:
            return None
        context, expires_at = entry
        if expires_at <= now:
            del _GUARD_SESSIONS[session_id]
            return None
        return context


async def get_guard_session_store() -> GuardSessionStore:
    global _guard_store
    if _guard_store is None:
        config = get_defend_config()
        ttl = config.guards.session_ttl_seconds
        _guard_store = GuardSessionStore(ttl_seconds=ttl)
    return _guard_store


