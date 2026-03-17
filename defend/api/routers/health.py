from fastapi import APIRouter, Response, status

from ..models.defend_qwen import get_defend_classifier
from ..pipeline.session_accumulator import get_session_accumulator
from ..providers import get_all_providers

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict:
    providers = {name: {"supports_modules": p.supports_modules} for name, p in get_all_providers().items()}
    return {"status": "ok", "providers": providers}


@router.get("/ready")
async def ready() -> Response:
    details: dict[str, str] = {}

    # Check L6 Defend model
    try:
        get_defend_classifier()
    except Exception as exc:  # pragma: no cover - defensive
        details["defend"] = f"error: {exc}"

    # Initialize session accumulator (L5, in-memory)
    try:
        await get_session_accumulator()
    except Exception as exc:  # pragma: no cover - defensive
        details["session_accumulator"] = f"error: {exc}"

    if details:
        return Response(
            content='{"status": "unready", "details": ' + str(details).replace("'", '"') + "}",
            media_type="application/json",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    return Response(content='{"status": "ready"}', media_type="application/json")

