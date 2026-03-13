from fastapi import APIRouter

from ..pipeline.orchestrator import run_pipeline
from ..schemas import ClassificationRequest, ClassificationResponse

router = APIRouter(prefix="/classify", tags=["classify"])


@router.post("", response_model=ClassificationResponse)
async def classify(request: ClassificationRequest) -> ClassificationResponse:
    result = await run_pipeline(request.text, request.session_id)
    return ClassificationResponse(
        is_injection=result.is_injection,
        final_action=result.final_action,
        layers=result.layers,
    )

