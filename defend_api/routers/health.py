from fastapi import APIRouter, Response, status

from ..models.defend_qwen import get_defend_classifier
from ..models.perplexity import get_perplexity_scorer
from ..pipeline.session_accumulator import get_session_accumulator

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@router.get("/ready")
async def ready() -> Response:
    details: dict[str, str] = {}

    # Check L4 perplexity model
    try:
        get_perplexity_scorer()
    except Exception as exc:  # pragma: no cover - defensive
        details["perplexity"] = f"error: {exc}"

    # Check L6 Defend model
    try:
        get_defend_classifier()
    except Exception as exc:  # pragma: no cover - defensive
        details["defend"] = f"error: {exc}"

    # Check Redis / session accumulator (L5)
    try:
        accumulator = await get_session_accumulator()
        # Light touch to force connection on first use.
        await accumulator._client.ping()  # type: ignore[attr-defined]
    except Exception as exc:  # pragma: no cover - defensive
        details["redis"] = f"error: {exc}"

    if details:
        return Response(
            content='{"status": "unready", "details": ' + str(details).replace("'", '"') + "}",
            media_type="application/json",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    return Response(content='{"status": "ready"}', media_type="application/json")

