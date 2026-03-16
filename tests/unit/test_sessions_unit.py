import pytest

from defend_api.pipeline.session_accumulator import _SESSION_STATE, get_session_accumulator
from defend_api.guard_session import get_guard_session_store


@pytest.mark.unit
@pytest.mark.asyncio
async def test_session_accumulator_in_memory_unit():
    _SESSION_STATE.clear()
    acc = await get_session_accumulator()

    session_id = "test-session"
    res1 = await acc.update(session_id, turn_score=0.5, threshold=0.9)
    assert res1.turns == 1

    res2 = await acc.update(session_id, turn_score=0.5, threshold=0.9)
    assert res2.turns == 2
    assert 0.0 <= res2.session_score <= 1.0


@pytest.mark.unit
@pytest.mark.asyncio
async def test_guard_session_store_in_memory_unit():
    store = await get_guard_session_store()
    session_id = "guard-session"
    context = {"text": "hello", "provider": "defend", "score": "0.4"}

    await store.save_input_context(session_id, context)
    loaded = await store.get_input_context(session_id)
    assert loaded == context

