"""Housing primitive builder — hollow cylindrical enclosure."""
from __future__ import annotations

from build123d import Cylinder, Part


def build_housing(inner_diameter_m: float, wall_thickness_m: float) -> Part:
    if inner_diameter_m <= 0:
        raise ValueError(f"inner_diameter must be positive, got {inner_diameter_m}")
    if wall_thickness_m <= 0:
        raise ValueError(f"wall_thickness must be positive, got {wall_thickness_m}")

    length_m = inner_diameter_m * 1.5
    inner_r_mm = (inner_diameter_m / 2) * 1000.0
    outer_r_mm = inner_r_mm + wall_thickness_m * 1000.0
    length_mm = length_m * 1000.0

    outer = Cylinder(radius=outer_r_mm, height=length_mm)
    inner = Cylinder(radius=inner_r_mm, height=length_mm * 1.1)
    return outer - inner
