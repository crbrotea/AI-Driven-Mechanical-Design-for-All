"""Mounting_Frame primitive builder — rectangular base plate."""
from __future__ import annotations

from build123d import Box, Part


def build_mounting_frame(length_m: float, width_m: float, height_m: float) -> Part:
    if length_m <= 0 or width_m <= 0 or height_m <= 0:
        raise ValueError(
            f"all dimensions must be positive; got "
            f"length={length_m}, width={width_m}, height={height_m}"
        )
    return Box(
        length=length_m * 1000.0,
        width=width_m * 1000.0,
        height=height_m * 1000.0,
    )
