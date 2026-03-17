from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ..session import SessionState, get_session_backend


@dataclass
class SessionResult:
    decision: str  # "BLOCK" | "ESCALATE" | "CONTINUE"
    session_score: float
    peak_score: float
    turns: int


class SessionAccumulator:
    async def load(self, session_id: str) -> Optional[SessionState]:
        backend = get_session_backend()
        return await backend.get(session_id)

    async def store(self, session_id: str, state: SessionState) -> None:
        backend = get_session_backend()
        await backend.update(state)

    async def clear(self, session_id: str) -> None:
        backend = get_session_backend()
        await backend.delete(session_id)

    async def update(self, session_id: str, turn_score: float, threshold: int) -> SessionResult:
        existing = await self.load(session_id)
        if existing is None:
            history = [turn_score]
            peak_score = turn_score
            rolling_score = turn_score
            risky_turns = 1 if turn_score >= 0.5 else 0
        else:
            history = existing.history + [turn_score]
            peak_score = max(existing.peak_score, turn_score)
            # Simple exponential decay on the last state.
            alpha = 0.7
            rolling_score = alpha * existing.rolling_score + (1 - alpha) * turn_score
            risky_turns = existing.risky_turns + (1 if turn_score >= 0.5 else 0)

        state = SessionState(
            session_id=session_id,
            history=history,
            peak_score=peak_score,
            rolling_score=rolling_score,
            risky_turns=risky_turns,
        )
        await self.store(session_id, state)

        # Block once the session has accumulated enough risky turns.
        decision = "BLOCK" if risky_turns >= threshold else "CONTINUE"

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

