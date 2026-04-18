"""SVG exporter — 2D front-elevation view for PDF reports."""
from __future__ import annotations

from pathlib import Path

from build123d import Compound, ExportSVG, Part

from services.geometry.domain.errors import GeometryError, GeometryErrorCode


def export_svg(part: Part | Compound, out_path: Path) -> None:
    """Export a front elevation view as SVG.

    build123d 0.10 does not expose a free-function ``export_svg``; instead it
    provides the ``ExportSVG`` class.  We use the builder pattern:

        exporter = ExportSVG()
        exporter.add_shape(part)
        exporter.write(path)

    ``section_xz()`` is also absent in 0.10, so the full 3-D shape is projected
    onto the XY plane (the default view).  The output is well-formed SVG XML
    starting with ``<?xml``.
    """
    try:
        exporter = ExportSVG()
        exporter.add_shape(part)
        exporter.write(str(out_path))
    except Exception as e:
        GeometryError(
            code=GeometryErrorCode.SVG_EXPORT_FAILED,
            message=f"SVG export failed: {e}",
            stage="export",
        ).raise_as()
