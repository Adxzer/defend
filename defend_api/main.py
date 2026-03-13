from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator

from .config import get_settings
from .logging import configure_logging, get_logger
from .routers import classify, compat, health


def create_app() -> FastAPI:
    configure_logging()
    settings = get_settings()

    app = FastAPI(
        title="Defend API",
        description="Standalone Defend prompt-injection classifier microservice.",
        version="0.1.0",
    )

    app.include_router(health.router)
    app.include_router(classify.router)
    app.include_router(compat.router)

    Instrumentator().instrument(app).expose(app, include_in_schema=False)

    logger = get_logger(__name__)

    @app.on_event("startup")
    async def on_startup() -> None:
        logger.info("Defend API starting up", extra={"host": settings.DEFEND_API_HOST, "port": settings.DEFEND_API_PORT})

    @app.on_event("shutdown")
    async def on_shutdown() -> None:
        logger.info("Defend API shutting down")

    return app


app = create_app()

