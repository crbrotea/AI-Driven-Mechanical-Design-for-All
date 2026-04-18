"""Unit tests for Shaft builder."""
from __future__ import annotations

import math

import pytest

from services.geometry.primitives.shaft import build_shaft


def test_volume_matches_cylinder_formula() -> None:
    diameter_m, length_m = 0.05, 0.5
    part = build_shaft(diameter_m, length_m)
    expected_v_m3 = math.pi * (diameter_m / 2) ** 2 * length_m
    actual_v_m3 = part.volume * 1e-9
    assert actual_v_m3 == pytest.approx(expected_v_m3, rel=0.02)


def test_bbox_matches_dimensions() -> None:
    part = build_shaft(diameter_m=0.05, length_m=0.5)
    bbox = part.bounding_box()
    assert pytest.approx(500.0, rel=0.01) == bbox.size.Z  # length in mm
    assert pytest.approx(50.0, rel=0.01) == bbox.size.X


def test_rejects_zero_diameter() -> None:
    with pytest.raises(ValueError):
        build_shaft(diameter_m=0.0, length_m=0.5)


def test_rejects_zero_length() -> None:
    with pytest.raises(ValueError):
        build_shaft(diameter_m=0.05, length_m=0.0)


def test_deterministic() -> None:
    p1 = build_shaft(0.05, 0.5)
    p2 = build_shaft(0.05, 0.5)
    assert p1.volume == pytest.approx(p2.volume, rel=1e-9)
