"""GLB exporter — tessellated geometry for web 3D viewers."""
from __future__ import annotations

from pathlib import Path

from build123d import Compound, Part
from build123d import export_gltf as _b3d_export_gltf

from services.geometry.domain.errors import GeometryError, GeometryErrorCode

# 1 mm — balance of fidelity and file size
DEFAULT_TESSELLATION_MM = 0.001  # linear_deflection is in model units (metres-ish)


def export_glb(
    part: Part | Compound,
    out_path: Path,
    tessellation_mm: float = DEFAULT_TESSELLATION_MM,
) -> None:
    """Export to GLB for web rendering (React Three Fiber).

    Uses build123d's free function ``export_gltf`` with ``binary=True``
    so the output is the compact binary GLB variant (magic bytes ``glTF``).
    """
    try:
        _b3d_export_gltf(
            part,
            str(out_path),
            binary=True,
            linear_deflection=tessellation_mm,
        )
    except Exception as e:
        GeometryError(
            code=GeometryErrorCode.GLB_EXPORT_FAILED,
            message=f"GLB export failed: {e}",
            stage="export",
        ).raise_as()
