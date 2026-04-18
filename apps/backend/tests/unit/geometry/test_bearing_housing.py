"""Unit tests for Bearing_Housing builder."""
from __future__ import annotations

import math

import pytest

from services.geometry.primitives.bearing_housing import build_bearing_housing


def test_volume_matches_hollow_cylinder() -> None:
    bore_m, outer_m = 0.05, 0.12
    part = build_bearing_housing(bore_diameter_m=bore_m, outer_diameter_m=outer_m)
    height_m = outer_m * 0.4  # builder derives height internally
    expected_v_m3 = math.pi / 4 * (outer_m**2 - bore_m**2) * height_m
    actual_v_m3 = part.volume * 1e-9
    assert actual_v_m3 == pytest.approx(expected_v_m3, rel=0.05)


def test_rejects_bore_ge_outer() -> None:
    with pytest.raises(ValueError):
        build_bearing_housing(bore_diameter_m=0.12, outer_diameter_m=0.12)


def test_bbox_matches_outer() -> None:
    part = build_bearing_housing(bore_diameter_m=0.05, outer_diameter_m=0.12)
    bbox = part.bounding_box()
    assert pytest.approx(120.0, rel=0.01) == bbox.size.X
