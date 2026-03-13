from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import redis.asyncio as redis

from ..config import get_settings


@dataclass
class SessionState:
    history: List[float]
    peak_score: float
    rolling_score: float


@dataclass
class SessionResult:
    decision: str  # "BLOCK" | "ESCALATE" | "CONTINUE"
    session_score: float
    peak_score: float
    turns: int


class SessionAccumulator:
    def __init__(self, client: redis.Redis) -> None:
        self._client = client

    @staticmethod
    def _key(session_id: str) -> str:
        return f"defend:session:{session_id}"

    async def load(self, session_id: str) -> Optional[SessionState]:
        raw: Optional[Dict[str, Any]] = await self._client.hgetall(self._key(session_id))  # type: ignore[assignment]
        if not raw:
            return None

        history = [float(x) for x in raw.get("history", "").split(",") if x]
        peak_score = float(raw.get("peak_score", 0.0))
        rolling_score = float(raw.get("rolling_score", 0.0))
        return SessionState(history=history, peak_score=peak_score, rolling_score=rolling_score)

    async def store(self, session_id: str, state: SessionState) -> None:
        await self._client.hset(
            self._key(session_id),
            mapping={
                "history": ",".join(str(s) for s in state.history),
                "peak_score": state.peak_score,
                "rolling_score": state.rolling_score,
            },
        )

    async def update(self, session_id: str, turn_score: float, threshold: float) -> SessionResult:
        existing = await self.load(session_id)
        if existing is None:
            history: List[float] = [turn_score]
            peak_score = turn_score
            rolling_score = turn_score
        else:
            history = existing.history + [turn_score]
            peak_score = max(existing.peak_score, turn_score)
            # Simple exponential decay on the last state.
            alpha = 0.7
            rolling_score = alpha * existing.rolling_score + (1 - alpha) * turn_score

        state = SessionState(history=history, peak_score=peak_score, rolling_score=rolling_score)
        await self.store(session_id, state)

        if rolling_score >= threshold:
            decision = "BLOCK"
        else:
            decision = "CONTINUE"

        return SessionResult(
            decision=decision,
            session_score=rolling_score,
            peak_score=peak_score,
            turns=len(history),
        )


_redis_client: Optional[redis.Redis] = None
_accumulator: Optional[SessionAccumulator] = None


async def get_session_accumulator() -> SessionAccumulator:
    global _redis_client, _accumulator
    if _accumulator is None:
        settings = get_settings()
        _redis_client = redis.from_url(settings.REDIS_URL)
        _accumulator = SessionAccumulator(_redis_client)
    return _accumulator

