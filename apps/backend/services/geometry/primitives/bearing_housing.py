"""Bearing_Housing primitive builder.

Height is derived as 40% of outer diameter (common ratio for pillow blocks).
"""
from __future__ import annotations

from build123d import Cylinder, Part


def build_bearing_housing(
    bore_diameter_m: float,
    outer_diameter_m: float,
) -> Part:
    if bore_diameter_m <= 0:
        raise ValueError(f"bore_diameter must be positive, got {bore_diameter_m}")
    if outer_diameter_m <= bore_diameter_m:
        raise ValueError(
            f"outer_diameter ({outer_diameter_m}) must exceed bore_diameter "
            f"({bore_diameter_m})"
        )

    height_m = outer_diameter_m * 0.4
    outer_r_mm = (outer_diameter_m / 2) * 1000.0
    bore_r_mm = (bore_diameter_m / 2) * 1000.0
    height_mm = height_m * 1000.0

    outer = Cylinder(radius=outer_r_mm, height=height_mm)
    bore = Cylinder(radius=bore_r_mm, height=height_mm * 1.1)
    return outer - bore
