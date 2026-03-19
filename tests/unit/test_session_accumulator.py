from __future__ import annotations

import anyio
import pytest

from defend_api.pipeline.session_accumulator import SessionAccumulator


def test_session_accumulator_decision_and_rolling_score() -> None:
    async def run() -> None:
        acc = SessionAccumulator()
        session_id = "unit-sess-1"

        # Threshold=2 means: 2+ risky turns (turn_score >= 0.5) -> BLOCK.
        r1 = await acc.update(session_id=session_id, turn_score=0.2, threshold=2)
        assert r1.decision == "CONTINUE"
        assert r1.turns == 1
        assert r1.peak_score == pytest.approx(0.2)
        assert r1.session_score == pytest.approx(0.2)

        r2 = await acc.update(session_id=session_id, turn_score=0.5, threshold=2)
        # rolling_score = 0.7*0.2 + 0.3*0.5 = 0.29
        assert r2.decision == "CONTINUE"
        assert r2.turns == 2
        assert r2.session_score == pytest.approx(0.29)
        assert r2.peak_score == pytest.approx(0.5)

        r3 = await acc.update(session_id=session_id, turn_score=0.5, threshold=2)
        # rolling_score = 0.7*0.29 + 0.3*0.5 = 0.353
        assert r3.decision == "BLOCK"
        assert r3.turns == 3
        assert r3.session_score == pytest.approx(0.353)
        assert r3.peak_score == pytest.approx(0.5)

    anyio.run(run)

