"""Tensor_Rod primitive builder.

A thin cylindrical rod used to tension foldable panels.

Governing formula: V = π * (d/2)² * L
"""
from __future__ import annotations

from build123d import Cylinder, Part


def build_tensor_rod(length_m: float, diameter_m: float) -> Part:
    """Build a tensioning rod (thin cylinder).

    Args:
        length_m: Rod length in meters.
        diameter_m: Rod diameter in meters.
    """
    if length_m <= 0:
        raise ValueError(f"length must be positive, got {length_m}")
    if diameter_m <= 0:
        raise ValueError(f"diameter must be positive, got {diameter_m}")

    radius_mm = (diameter_m / 2) * 1000.0
    length_mm = length_m * 1000.0
    return Cylinder(radius=radius_mm, height=length_mm)
