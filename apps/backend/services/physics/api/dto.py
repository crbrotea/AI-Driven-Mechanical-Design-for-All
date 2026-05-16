"""Request DTO for the physics API."""
from __future__ import annotations

from pydantic import BaseModel

from services.interpreter.domain.intent import DesignIntent


class AnalyzeRequest(BaseModel):
    intent: DesignIntent
    material_name: str | None = None
