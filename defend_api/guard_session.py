from __future__ import annotations

from typing import Any, Dict, Optional

import redis.asyncio as redis

from .config import get_defend_config, get_settings


class GuardSessionStore:
    def __init__(self, client: redis.Redis, ttl_seconds: int) -> None:
        self._client = client
        self._ttl = ttl_seconds

    @staticmethod
    def _key(session_id: str) -> str:
        return f"guard:session:{session_id}"

    async def save_input_context(self, session_id: str, context: Dict[str, Any]) -> None:
        await self._client.hset(self._key(session_id), mapping=context)
        await self._client.expire(self._key(session_id), self._ttl)

    async def get_input_context(self, session_id: str) -> Optional[Dict[str, Any]]:
        raw: Dict[bytes, bytes] = await self._client.hgetall(self._key(session_id))  # type: ignore[assignment]
        if not raw:
            return None
        return {k.decode("utf-8"): v.decode("utf-8") for k, v in raw.items()}


_guard_client: Optional[redis.Redis] = None
_guard_store: Optional[GuardSessionStore] = None


async def get_guard_session_store() -> GuardSessionStore:
    global _guard_client, _guard_store
    if _guard_store is None:
        settings = get_settings()
        config = get_defend_config()
        _guard_client = redis.from_url(settings.REDIS_URL)
        ttl = config.guards.session_ttl_seconds
        _guard_store = GuardSessionStore(_guard_client, ttl)
    return _guard_store


