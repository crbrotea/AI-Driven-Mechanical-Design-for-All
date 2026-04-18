"""Unit tests for Flywheel_Rim builder."""
from __future__ import annotations

import math

import pytest

from services.geometry.primitives.flywheel_rim import build_flywheel_rim


def test_volume_matches_analytical_formula() -> None:
    outer_m, inner_m, thickness_m = 0.5, 0.1, 0.05
    part = build_flywheel_rim(outer_m, inner_m, thickness_m)
    expected_v_m3 = math.pi / 4 * (outer_m**2 - inner_m**2) * thickness_m
    actual_v_m3 = part.volume * 1e-9  # build123d uses mm³
    assert actual_v_m3 == pytest.approx(expected_v_m3, rel=0.05)


def test_bbox_matches_outer_diameter() -> None:
    part = build_flywheel_rim(0.5, 0.1, 0.05)
    bbox = part.bounding_box()
    assert pytest.approx(500.0, rel=0.01) == bbox.size.X  # mm
    assert pytest.approx(50.0, rel=0.01) == bbox.size.Z


def test_rejects_inner_ge_outer() -> None:
    with pytest.raises(ValueError, match="inner_diameter"):
        build_flywheel_rim(outer_diameter_m=0.1, inner_diameter_m=0.2, thickness_m=0.05)


def test_rejects_zero_thickness() -> None:
    with pytest.raises(ValueError):
        build_flywheel_rim(outer_diameter_m=0.5, inner_diameter_m=0.1, thickness_m=0.0)


def test_deterministic() -> None:
    p1 = build_flywheel_rim(0.5, 0.1, 0.05)
    p2 = build_flywheel_rim(0.5, 0.1, 0.05)
    assert p1.volume == pytest.approx(p2.volume, rel=1e-9)
