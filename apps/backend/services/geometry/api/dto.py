"""HTTP request/response DTOs for the Geometry API."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from services.geometry.domain.artifacts import MassProperties
from services.interpreter.domain.intent import DesignIntent


class GenerateRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    intent: DesignIntent
    session_id: str | None = None
    material_name: str = "steel_a36"  # default if not specified


class GenerateArtifactUrls(BaseModel):
    model_config = ConfigDict(frozen=True)

    step_url: str
    glb_url: str
    svg_url: str


class GenerateResponse(BaseModel):
    """Body of the `final` SSE event and GET /artifacts."""

    model_config = ConfigDict(frozen=True)

    cache_hit: bool
    intent_hash: str
    artifacts: GenerateArtifactUrls
    mass_properties: MassProperties
    material_name: str
    material_density_kg_m3: float
