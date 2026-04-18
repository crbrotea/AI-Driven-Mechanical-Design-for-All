"""Flywheel Rim primitive builder.

Governing formula: V = π/4 * (D² - d²) * t
where D = outer_diameter, d = inner_diameter, t = thickness.
"""
from __future__ import annotations

import math

from build123d import Cylinder, GeomType, Part, fillet


def build_flywheel_rim(
    outer_diameter_m: float,
    inner_diameter_m: float,
    thickness_m: float,
    rpm: float | None = None,  # accepted but unused for geometry
) -> Part:
    """Build a hollow disk with mass concentrated at the periphery.

    Args:
        outer_diameter_m: Outer diameter in meters.
        inner_diameter_m: Inner hole diameter in meters.
        thickness_m: Axial thickness in meters.
        rpm: Accepted for API uniformity; not used for geometry.

    Returns:
        A build123d Part representing the flywheel rim (in mm internally).
    """
    if inner_diameter_m >= outer_diameter_m:
        raise ValueError(
            f"inner_diameter ({inner_diameter_m}) must be smaller than "
            f"outer_diameter ({outer_diameter_m})"
        )
    if thickness_m <= 0:
        raise ValueError(f"thickness must be positive, got {thickness_m}")

    # build123d operates in mm by default
    outer_r_mm = (outer_diameter_m / 2) * 1000.0
    inner_r_mm = (inner_diameter_m / 2) * 1000.0
    thickness_mm = thickness_m * 1000.0

    outer = Cylinder(radius=outer_r_mm, height=thickness_mm)
    inner = Cylinder(radius=inner_r_mm, height=thickness_mm * 1.1)
    rim = outer - inner

    # Small fillet on outer circular edges for FEA-friendly mesh.
    # filter_by(Axis.Z) selects LINE edges (vertical walls); we need CIRCLE
    # edges on the outer diameter, identified by circumference > midpoint
    # between inner and outer circumferences.
    inner_circ = 2 * math.pi * inner_r_mm
    outer_circ = 2 * math.pi * outer_r_mm
    length_threshold = (inner_circ + outer_circ) / 2
    outer_circle_edges = [
        e
        for e in rim.edges()
        if e.geom_type == GeomType.CIRCLE and e.length > length_threshold
    ]

    fillet_radius = min(5.0, thickness_mm / 10.0)
    if fillet_radius > 0 and outer_circle_edges:
        rim = fillet(outer_circle_edges, radius=fillet_radius)

    return rim
