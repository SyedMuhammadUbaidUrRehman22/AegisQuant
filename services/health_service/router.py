"""HTTP routes for liveness and the Stage 0 hello-world response."""

from fastapi import APIRouter, Request, status

from config.settings import Settings
from services.health_service.schemas import ServiceResponse

router = APIRouter()


def _response(request: Request) -> ServiceResponse:
    """Build the service response from validated startup settings."""

    settings: Settings = request.app.state.settings
    return ServiceResponse(
        service=settings.app.name,
        status="ok",
        version=request.app.version,
        environment=settings.app.environment,
    )


@router.get("/", response_model=ServiceResponse, status_code=status.HTTP_200_OK)
def hello(request: Request) -> ServiceResponse:
    """Return the minimal Stage 0 hello-world service contract."""

    return _response(request)


@router.get("/health", response_model=ServiceResponse, status_code=status.HTTP_200_OK)
def health(request: Request) -> ServiceResponse:
    """Report process liveness without claiming database readiness."""

    return _response(request)
