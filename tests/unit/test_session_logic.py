import time

import pytest

from defend_api.pipeline.session_accumulator import SessionAccumulator
from defend_api.guard_session import GuardSessionStore


@pytest.mark.unit
@pytest.mark.asyncio
async def test_session_accumulator_multiple_sessions_independent():
    acc = SessionAccumulator()

    res1 = await acc.update("s1", turn_score=0.2, threshold=0.9)
    res2 = await acc.update("s2", turn_score=0.8, threshold=0.9)
    assert res1.turns == 1
    assert res2.turns == 1
    assert res1.decision == "CONTINUE"
    assert res2.decision == "CONTINUE"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_session_accumulator_blocks_when_threshold_reached():
    acc = SessionAccumulator()

    # First update below threshold.
    await acc.update("s3", turn_score=0.5, threshold=0.6)
    # Second update should push rolling score above threshold.
    res = await acc.update("s3", turn_score=1.0, threshold=0.6)
    assert res.decision == "BLOCK"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_guard_session_store_ttl_expires(monkeypatch):
    store = GuardSessionStore(ttl_seconds=1)
    sid = "session-ttl"
    ctx = {"text": "hello"}

    await store.save_input_context(sid, ctx)
    # Before expiry
    assert await store.get_input_context(sid) == ctx

    # Fast-forward time beyond TTL
    future = time.time() + 2
    monkeypatch.setattr("defend_api.guard_session.time.time", lambda: future)

    assert await store.get_input_context(sid) is None

