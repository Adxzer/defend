from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional


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


# Per-process, non-durable session storage.
_SESSION_STATE: Dict[str, SessionState] = {}


class SessionAccumulator:
    async def load(self, session_id: str) -> Optional[SessionState]:
        return _SESSION_STATE.get(session_id)

    async def store(self, session_id: str, state: SessionState) -> None:
        _SESSION_STATE[session_id] = state

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


_accumulator: Optional[SessionAccumulator] = None


async def get_session_accumulator() -> SessionAccumulator:
    global _accumulator
    if _accumulator is None:
        _accumulator = SessionAccumulator()
    return _accumulator

