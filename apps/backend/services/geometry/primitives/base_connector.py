"""Base_Connector primitive builder.

A square-cross-section block used to attach panels to a ground plate.

Governing formula: V = width_m² * height_m
"""
from __future__ import annotations

from build123d import Box, Part


def build_base_connector(width_m: float, height_m: float) -> Part:
    """Build a base connector block (square cross-section).

    Args:
        width_m: Width (and depth) of the connector in meters. Defines both X and Y extent.
        height_m: Height (Z extent) of the connector in meters.
    """
    if width_m <= 0:
        raise ValueError(f"width must be positive, got {width_m}")
    if height_m <= 0:
        raise ValueError(f"height must be positive, got {height_m}")

    return Box(
        length=width_m * 1000.0,
        width=width_m * 1000.0,
        height=height_m * 1000.0,
    )
