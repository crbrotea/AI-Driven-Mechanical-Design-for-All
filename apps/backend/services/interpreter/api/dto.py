"""HTTP request/response DTOs for the Interpreter API."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from services.interpreter.domain.intent import DesignIntent


class InterpretRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    prompt: str = Field(min_length=1, max_length=2000)
    session_id: str | None = None


class RefineRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    session_id: str
    field_updates: dict[str, Any]


class InterpretResponse(BaseModel):
    """Body of the `final` SSE event and the GET /sessions response."""

    model_config = ConfigDict(frozen=True)

    session_id: str
    intent: DesignIntent
    language: str  # "es" | "en"
