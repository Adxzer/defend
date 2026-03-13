from fastapi import APIRouter

from ..schemas import ClassificationRequest, ClassificationResponse
from ..pipeline.orchestrator import run_pipeline


router = APIRouter(prefix="", tags=["compat"])


@router.get("/models")
async def list_models() -> dict:
    # Minimal compatibility endpoint mirroring a simple model listing.
    return {"data": [{"id": "defend-classifier", "object": "model"}]}


@router.post("/invoke", response_model=ClassificationResponse)
async def invoke(request: ClassificationRequest) -> ClassificationResponse:
    result = await run_pipeline(request.text, request.session_id)
    return ClassificationResponse(
        is_injection=result.is_injection,
        final_action=result.final_action,
        layers=result.layers,
    )

