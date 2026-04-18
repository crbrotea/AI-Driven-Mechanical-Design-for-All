"""Artifact domain models for the Geometry service."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class MassProperties(BaseModel):
    """Computed mass/inertia properties of a geometry.

    All values are SI: volume in m³, mass in kg, positions/bbox in m.
    """

    model_config = ConfigDict(frozen=True)

    volume_m3: float
    mass_kg: float
    center_of_mass: tuple[float, float, float]
    bbox_m: tuple[float, float, float, float, float, float]
    # bbox: (min_x, min_y, min_z, max_x, max_y, max_z)


class BuiltArtifacts(BaseModel):
    """In-memory artifacts freshly built from a DesignIntent."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    step_bytes: bytes
    glb_bytes: bytes
    svg_bytes: bytes
    mass: MassProperties


class CachedArtifacts(BaseModel):
    """Cached artifacts addressable via signed URLs."""

    model_config = ConfigDict(frozen=True)

    mass_properties: MassProperties
    step_url: str
    glb_url: str
    svg_url: str
