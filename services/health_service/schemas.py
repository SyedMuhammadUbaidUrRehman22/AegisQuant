"""Response contracts for the Stage 0 health service."""

from typing import Literal

from pydantic import BaseModel, ConfigDict


class ServiceResponse(BaseModel):
    """Stable response contract for the root and health endpoints."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    service: str
    status: Literal["ok"]
    version: str
    environment: Literal["development", "production"]
