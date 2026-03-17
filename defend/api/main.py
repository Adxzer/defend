from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator

from .config import get_defend_config, get_settings
from .logging import configure_logging, get_logger
from .models.defend_qwen import get_defend_classifier
from .models.intent import get_intent_classifier
from .providers.orchestrator import get_provider_orchestrator
from .routers import guard, health, sessions


def create_app() -> FastAPI:
    configure_logging()
    settings = get_settings()

    app = FastAPI(
        title="Defend API",
        description="Standalone Defend guardrail microservice.",
        version="0.1.0",
    )

    # v1 routes (current)
    app.include_router(health.router, prefix="/v1")
    app.include_router(guard.router, prefix="/v1")
    app.include_router(sessions.router, prefix="/v1")

    # Expose metrics under /v1 to match the API versioning scheme.
    Instrumentator().instrument(app).expose(app, endpoint="/v1/metrics", include_in_schema=False)

    logger = get_logger(__name__)

    @app.on_event("startup")
    async def on_startup() -> None:
        logger.info(
            "Defend API starting up",
            extra={"host": settings.DEFEND_API_HOST, "port": settings.DEFEND_API_PORT},
        )

        # Eagerly load core models/providers to avoid slow first request.
        defend_config = get_defend_config()

        # Intent fast-pass model (L2) – eager load to avoid cold-start on first /guard/input.
        get_intent_classifier()

        # Provider orchestrator (L6)
        get_provider_orchestrator()

        # Defend classifier only when configured as primary or fallback provider.
        if defend_config.provider.primary == "defend" or defend_config.provider.fallback == "defend":
            get_defend_classifier()

    @app.on_event("shutdown")
    async def on_shutdown() -> None:
        logger.info("Defend API shutting down")

    return app


app = create_app()


