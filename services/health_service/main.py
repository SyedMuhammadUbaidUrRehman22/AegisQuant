"""FastAPI application factory for the Stage 0 health service."""

from fastapi import FastAPI

from config.settings import Settings, get_settings
from services.health_service.router import router

SERVICE_VERSION = "0.0.1"


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create a stateless health service using validated configuration."""

    resolved_settings = settings or get_settings()
    application = FastAPI(
        title=f"{resolved_settings.app.name} Health Service",
        description="Stage 0 liveness and hello-world service.",
        version=SERVICE_VERSION,
    )
    application.state.settings = resolved_settings
    application.include_router(router)
    return application


app = create_app()
