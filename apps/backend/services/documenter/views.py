"""Project a build123d Compound onto 2D views as SVG bytes."""
from __future__ import annotations

import tempfile
from pathlib import Path

from build123d import Compound, Vector

from services.documenter.domain.errors import (
    DocumentError,
    DocumentErrorCode,
)

# Each entry is the camera/viewport origin direction (unit vector). We scale by
# _VIEWPORT_DISTANCE before projecting so the orthographic camera sits outside
# any plausible part bounding box.
_VIEW_DIRECTIONS: dict[str, Vector] = {
    "front": Vector(0, 0, -1),     # camera on z- looking back at origin
    "side": Vector(1, 0, 0),       # camera on x+ looking back at origin
    "iso": Vector(1, 1, 1),        # camera on iso ray, orthographic
}

_TOP_VIEW = Vector(0, 1, 0)        # fallback when iso fails (camera on y+)

# Pull the viewport far enough that the part bounding box is always in front
# of the camera. Build123d uses world units (mm by default).
_VIEWPORT_DISTANCE = 1000.0


def project_views(compound: Compound) -> dict[str, bytes]:
    """Project the compound onto 3 view directions. Return SVG byte blobs.

    Keys: "front", "side", "iso". If 'iso' projection raises, substitute a
    'top' view but keep the key as 'iso' so downstream consumers are agnostic.
    Failures of 'front' or 'side' raise VIEW_PROJECTION_FAILED.
    """
    out: dict[str, bytes] = {}
    for name, vec in _VIEW_DIRECTIONS.items():
        try:
            out[name] = _export_svg(compound, vec)
        except Exception as exc:
            if name == "iso":
                try:
                    out["iso"] = _export_svg(compound, _TOP_VIEW)
                    continue
                except Exception as inner:
                    DocumentError(
                        code=DocumentErrorCode.VIEW_PROJECTION_FAILED,
                        message=f"projection 'iso' (and top fallback) failed: {inner!r}",
                        stage="project_views",
                        details={"primary": repr(exc), "fallback": repr(inner)},
                    ).raise_as()
            DocumentError(
                code=DocumentErrorCode.VIEW_PROJECTION_FAILED,
                message=f"projection {name!r} failed: {exc!r}",
                stage="project_views",
                details={"view": name},
            ).raise_as()
    return out


def _export_svg(compound: Compound, view_vector: Vector) -> bytes:
    """Write compound to an SVG file via build123d ExportSVG, read bytes back.

    build123d 0.10's ExportSVG always projects onto the XY plane; to produce
    front/side/iso views we first call ``Compound.project_to_viewport`` with
    the supplied direction, then hand the resulting visible Edges (which lie
    in the viewport's XY plane) to ExportSVG. NamedTemporaryFile captures
    bytes without leaking files to the workspace.
    """
    from build123d import ExportSVG  # local import to keep module import light

    # Camera sits along view_vector at _VIEWPORT_DISTANCE; orthographic
    # projection (focus=None) returns visible edges in 2D viewport coords.
    viewport_origin = Vector(view_vector) * _VIEWPORT_DISTANCE
    visible, _hidden = compound.project_to_viewport(viewport_origin)

    with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as tf:
        tmp_path = Path(tf.name)
    try:
        exporter = ExportSVG()
        exporter.add_shape(list(visible))
        exporter.write(str(tmp_path))
        return tmp_path.read_bytes()
    finally:
        tmp_path.unlink(missing_ok=True)
