"""STEP AP214 exporter — universal CAD download format."""
from __future__ import annotations

from pathlib import Path

from build123d import Compound, Part
from build123d import export_step as _b3d_export_step

from services.geometry.domain.errors import GeometryError, GeometryErrorCode


def export_step(part: Part | Compound, out_path: Path) -> None:
    """Export to STEP AP214. Raises GeometryException on failure."""
    try:
        _b3d_export_step(part, str(out_path))
    except Exception as e:
        GeometryError(
            code=GeometryErrorCode.STEP_EXPORT_FAILED,
            message=f"STEP export failed: {e}",
            stage="export",
        ).raise_as()
