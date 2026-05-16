"""Domain models for S4 Explainer."""
from __future__ import annotations

from pydantic import BaseModel, Field

from services.interpreter.domain.intent import DesignIntent
from services.physics.domain.models import AnalysisResult


class NaturalReport(BaseModel):
    """Structured natural-language report. Output of S4."""

    summary: str = Field(..., description="<=80 word plain-English summary")
    risks: list[str] = Field(default_factory=list, description="1-4 short bullets")
    suggestions: list[str] = Field(default_factory=list, description="1-4 actionable bullets")
    analogies: list[str] = Field(default_factory=list, description="1-2 lay analogies")
    facts_used: list[str] = Field(default_factory=list, description="exact FACTS labels cited")


class ExplainRequest(BaseModel):
    """Request body for POST /explain."""

    intent: DesignIntent
    analysis_result: AnalysisResult
    session_id: str | None = None
