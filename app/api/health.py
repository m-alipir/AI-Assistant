"""Liveness and dependency-readiness endpoints."""

from collections.abc import Awaitable, Callable

from fastapi import APIRouter, Request, Response, status
from pydantic import BaseModel

router = APIRouter(tags=["system"])


class HealthResponse(BaseModel):
    """Small health payload with no configuration or secret information."""

    status: str


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Report that the API process can serve requests."""
    return HealthResponse(status="ok")


@router.get("/ready", response_model=HealthResponse)
async def ready(request: Request, response: Response) -> HealthResponse:
    """Report dependency readiness, returning 503 until the database is usable."""
    readiness_check: Callable[[], Awaitable[bool]] = request.app.state.readiness_check
    if await readiness_check():
        return HealthResponse(status="ready")
    response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return HealthResponse(status="not_ready")
