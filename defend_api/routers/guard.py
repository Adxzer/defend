from __future__ import annotations

import math
import uuid
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from ..guard_session import get_guard_session_store
from ..pipeline.orchestrator import run_pipeline
from ..schemas import GuardInputRequest, GuardOutputRequest, GuardResult


router = APIRouter(prefix="/guard", tags=["guard"])


def _sanitize_finite(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _sanitize_finite(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize_finite(v) for v in obj]
    if isinstance(obj, float) and not math.isfinite(obj):
        return 0.0
    return obj


@router.post("/input", response_model=GuardResult)
async def guard_input(request: GuardInputRequest) -> JSONResponse:
    # Run the existing pipeline; this already goes through providers & modules.
    pipeline_result = await run_pipeline(request.text, request.session_id)

    session_id = request.session_id or f"def-{uuid.uuid4().hex[:8]}"
    store = await get_guard_session_store()
    context: Dict[str, Any] = {
        "text": request.text,
        "provider": pipeline_result.decided_by or "defend",
        "score": pipeline_result.score if pipeline_result.score is not None else "",
    }
    await store.save_input_context(session_id, context)

    action = "block" if pipeline_result.final_action == pipeline_result.final_action.BLOCK else "pass"

    result = GuardResult(
        action=action,
        session_id=session_id,
        decided_by=pipeline_result.decided_by or "defend",
        direction="input",
        score=pipeline_result.score,
        reason=pipeline_result.reason,
        modules_triggered=pipeline_result.modules_triggered or [],
        context="none",
        latency_ms=pipeline_result.latency_ms or 0,
    )

    payload = _sanitize_finite(result.model_dump())
    return JSONResponse(content=payload)


@router.post("/output", response_model=GuardResult)
async def guard_output(request: GuardOutputRequest) -> JSONResponse:
    store = await get_guard_session_store()
    input_context = None
    context_flag: str = "none"

    if request.session_id:
        input_context = await store.get_input_context(request.session_id)
        if input_context:
            context_flag = "session"

    # For now, reuse run_pipeline to get provider decision on output text only.
    # A later iteration can introduce a dedicated output-evaluation path that
    # passes both input and output to the provider.
    pipeline_result = await run_pipeline(request.text, None)

    if pipeline_result.decided_by == "defend":
        # Enforce that output guarding uses an LLM provider only.
        raise HTTPException(
            status_code=400,
            detail="Output guarding requires an LLM provider (claude or openai). adxzer/defend only supports input evaluation.",
        )

    session_id = request.session_id or f"def-{uuid.uuid4().hex[:8]}"
    action = "block" if pipeline_result.final_action == pipeline_result.final_action.BLOCK else "pass"

    result = GuardResult(
        action=action,
        session_id=session_id,
        decided_by=pipeline_result.decided_by or "defend",
        direction="output",
        score=pipeline_result.score,
        reason=pipeline_result.reason,
        modules_triggered=pipeline_result.modules_triggered or [],
        context=context_flag,  # "session" if input context was used
        latency_ms=pipeline_result.latency_ms or 0,
    )

    payload = _sanitize_finite(result.model_dump())
    return JSONResponse(content=payload)

