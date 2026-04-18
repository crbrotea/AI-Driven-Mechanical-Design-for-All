"""Shaft primitive builder.

Governing formula: V = π * (d/2)² * L
"""
from __future__ import annotations

from build123d import Cylinder, Part


def build_shaft(diameter_m: float, length_m: float) -> Part:
    """Build a cylindrical rotating shaft.

    Args:
        diameter_m: Shaft diameter in meters.
        length_m: Shaft length along the rotation axis in meters.
    """
    if diameter_m <= 0:
        raise ValueError(f"diameter must be positive, got {diameter_m}")
    if length_m <= 0:
        raise ValueError(f"length must be positive, got {length_m}")

    radius_mm = (diameter_m / 2) * 1000.0
    length_mm = length_m * 1000.0
    return Cylinder(radius=radius_mm, height=length_mm)
