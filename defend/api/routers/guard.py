from __future__ import annotations

import math
import uuid
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from ..config import get_defend_config
from ..guard_session import get_guard_session_store
from ..modules import build_modules_from_specs
from ..providers import get_provider
from ..providers.base import ProviderUnavailableError
from ..schemas import GuardAction, GuardContext, GuardInputRequest, GuardOutputRequest, GuardResult, GuardResultVerbose


router = APIRouter(prefix="/guard", tags=["guard"])


def _sanitize_finite(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _sanitize_finite(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize_finite(v) for v in obj]
    if isinstance(obj, float) and not math.isfinite(obj):
        return 0.0
    return obj


def _map_final_action_to_guard_action(final_action: Any) -> GuardAction:
    value = getattr(final_action, "value", None)
    if value == "BLOCK":
        return GuardAction.BLOCK
    if value == "LOG":
        return GuardAction.FLAG
    return GuardAction.PASS


def _format_output_eval_text(output_text: str, input_context: Optional[Dict[str, Any]]) -> str:
    if not input_context or not input_context.get("text"):
        return output_text
    user_text = str(input_context.get("text", ""))
    return f"ORIGINAL_USER_INPUT:\n{user_text}\n\nLLM_RESPONSE:\n{output_text}"


@router.post("/input", response_model=GuardResult | GuardResultVerbose)
async def guard_input(request: GuardInputRequest, verbose: bool = False) -> JSONResponse:
    # Reject excessively large payloads early to avoid timeouts and unnecessary downstream work.
    if len(request.text) >= 20_000:
        raise HTTPException(status_code=413, detail="Input text too large")

    from ..pipeline.orchestrator import run_pipeline

    session_id = request.session_id or f"def-{uuid.uuid4().hex[:8]}"
    # Run the pipeline with a session id so L5 applies on first turn.
    pipeline_result = await run_pipeline(request.text, session_id)
    store = await get_guard_session_store()
    context: Dict[str, Any] = {
        "text": request.text,
        "provider": pipeline_result.decided_by or "defend",
        "score": pipeline_result.score,
    }
    await store.save_input_context(session_id, context)

    action = _map_final_action_to_guard_action(pipeline_result.final_action)

    result = GuardResult(
        action=action,
        session_id=session_id,
        decided_by=pipeline_result.decided_by or "defend",
        direction="input",
        score=pipeline_result.score,
        reason=pipeline_result.reason,
        modules_triggered=pipeline_result.modules_triggered or [],
        context=GuardContext.NONE,
        latency_ms=pipeline_result.latency_ms or 0,
    )

    if verbose:
        verbose_result = GuardResultVerbose(
            **result.model_dump(),
            is_injection=pipeline_result.is_injection,
            final_action=pipeline_result.final_action,
            layers=pipeline_result.layers,
        )
        payload = _sanitize_finite(verbose_result.model_dump())
    else:
        payload = _sanitize_finite(result.model_dump())
    return JSONResponse(content=payload)


@router.post("/output", response_model=GuardResult)
async def guard_output(request: GuardOutputRequest) -> JSONResponse:
    config = get_defend_config()
    store = await get_guard_session_store()
    input_context = None
    context_flag: GuardContext = GuardContext.NONE

    # Allow explicit disabling of output guarding (useful for defend-only setups).
    if getattr(config.guards.output, "enabled", True) is False:
        session_id = request.session_id or f"def-{uuid.uuid4().hex[:8]}"
        result = GuardResult(
            action=GuardAction.PASS,
            session_id=session_id,
            decided_by="disabled",
            direction="output",
            score=None,
            reason=None,
            modules_triggered=[],
            context=GuardContext.NONE,
            latency_ms=0,
        )
        return JSONResponse(content=_sanitize_finite(result.model_dump()))

    if request.session_id:
        input_context = await store.get_input_context(request.session_id)
        if input_context:
            context_flag = GuardContext.SESSION

    provider_name = config.guards.output.provider
    provider = get_provider(provider_name)
    if provider_name.value == "defend" or not provider.supports_modules:
        raise HTTPException(status_code=400, detail="Output guarding requires an LLM provider (claude or openai).")

    modules = build_modules_from_specs(config.guards.output.modules or [])
    modules = [m for m in modules if m.direction in ("output", "both")]
    eval_text = _format_output_eval_text(request.text, input_context)

    try:
        provider_result = await provider.evaluate(text=eval_text, session_id=request.session_id, modules=modules)
        action = provider_result.action
        decided_by = provider_result.provider
        score = provider_result.score
        reason = provider_result.reason
        modules_triggered = provider_result.modules_triggered or []
        latency_ms = provider_result.latency_ms or 0
    except ProviderUnavailableError as exc:
        action = config.guards.output.on_fail
        decided_by = provider_name.value
        score = None
        reason = str(exc)
        modules_triggered = []
        latency_ms = 0

    session_id = request.session_id or f"def-{uuid.uuid4().hex[:8]}"

    result = GuardResult(
        action=action,
        session_id=session_id,
        decided_by=decided_by,
        direction="output",
        score=score,
        reason=reason,
        modules_triggered=modules_triggered,
        context=context_flag,  # "session" if input context was used
        latency_ms=latency_ms,
    )

    payload = _sanitize_finite(result.model_dump())
    return JSONResponse(content=payload)

