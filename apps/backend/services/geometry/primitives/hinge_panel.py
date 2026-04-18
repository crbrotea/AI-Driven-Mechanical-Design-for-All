"""Hinge_Panel primitive — rigid panel hinged at one edge."""
from __future__ import annotations

from build123d import Box, Part


def build_hinge_panel(width_m: float, height_m: float, thickness_m: float) -> Part:
    if width_m <= 0 or height_m <= 0 or thickness_m <= 0:
        raise ValueError(
            f"all dimensions must be positive; got "
            f"width={width_m}, height={height_m}, thickness={thickness_m}"
        )
    return Box(
        length=width_m * 1000.0,
        width=height_m * 1000.0,
        height=thickness_m * 1000.0,
    )
