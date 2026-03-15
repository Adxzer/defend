import math
from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from ..pipeline.orchestrator import run_pipeline
from ..schemas import ClassificationRequest, ClassificationResponse

router = APIRouter(prefix="/classify", tags=["classify"])


def _sanitize_finite(obj: Any) -> Any:
    """Replace non-finite floats so the payload is JSON-compliant."""
    if isinstance(obj, dict):
        return {k: _sanitize_finite(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize_finite(v) for v in obj]
    if isinstance(obj, float) and not math.isfinite(obj):
        return 0.0
    return obj


@router.post("", response_model=ClassificationResponse)
async def classify(request: ClassificationRequest) -> JSONResponse:
    result = await run_pipeline(request.text, request.session_id)
    response = ClassificationResponse(
        is_injection=result.is_injection,
        final_action=result.final_action,
        layers=result.layers,
    )
    payload = _sanitize_finite(response.model_dump())
    return JSONResponse(content=payload)

