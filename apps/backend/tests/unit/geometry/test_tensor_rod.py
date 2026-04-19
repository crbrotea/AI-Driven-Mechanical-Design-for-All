"""Unit tests for Tensor_Rod builder."""
from __future__ import annotations

import math

import pytest

from services.geometry.primitives.tensor_rod import build_tensor_rod


def test_volume_matches_cylinder_formula() -> None:
    length_m, diameter_m = 2.0, 0.01
    part = build_tensor_rod(length_m=length_m, diameter_m=diameter_m)
    expected_v_m3 = math.pi * (diameter_m / 2) ** 2 * length_m
    actual_v_m3 = part.volume * 1e-9
    assert pytest.approx(expected_v_m3, rel=0.02) == actual_v_m3


def test_bbox_matches_dimensions() -> None:
    part = build_tensor_rod(length_m=2.0, diameter_m=0.01)
    bbox = part.bounding_box()
    assert pytest.approx(2000.0, rel=0.01) == bbox.size.Z  # length along Z
    assert pytest.approx(10.0, rel=0.01) == bbox.size.X


def test_rejects_zero_length() -> None:
    with pytest.raises(ValueError):
        build_tensor_rod(length_m=0.0, diameter_m=0.01)


def test_rejects_zero_diameter() -> None:
    with pytest.raises(ValueError):
        build_tensor_rod(length_m=2.0, diameter_m=0.0)
