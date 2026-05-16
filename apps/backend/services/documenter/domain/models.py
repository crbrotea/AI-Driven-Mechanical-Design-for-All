"""Domain models for S5 Documenter."""
from __future__ import annotations

from pydantic import BaseModel

from services.explainer.domain.models import NaturalReport
from services.geometry.domain.artifacts import CachedArtifacts
from services.interpreter.domain.intent import DesignIntent
from services.physics.domain.models import AnalysisResult


class DocumentRequest(BaseModel):
    """Request body for POST /document."""

    intent: DesignIntent
    analysis_result: AnalysisResult
    natural_report: NaturalReport
    geometry_artifacts: CachedArtifacts
    session_id: str | None = None


class Deliverables(BaseModel):
    """Response body of POST /document. Bundles all 5 artifact URLs."""

    report_pdf_url: str
    drawing_pdf_url: str
    step_url: str
    glb_url: str
    svg_url: str
    cache_hit: bool
    cache_key: str
