"""Unit tests for Base_Connector builder."""
from __future__ import annotations

import pytest

from services.geometry.primitives.base_connector import build_base_connector


def test_volume_matches_box_formula() -> None:
    width_m, height_m = 0.04, 0.02
    part = build_base_connector(width_m=width_m, height_m=height_m)
    expected_v_m3 = width_m * width_m * height_m
    actual_v_m3 = part.volume * 1e-9
    assert pytest.approx(expected_v_m3, rel=0.02) == actual_v_m3


def test_bbox_matches_dimensions() -> None:
    part = build_base_connector(width_m=0.04, height_m=0.02)
    bbox = part.bounding_box()
    assert pytest.approx(40.0, rel=0.01) == bbox.size.X
    assert pytest.approx(40.0, rel=0.01) == bbox.size.Y
    assert pytest.approx(20.0, rel=0.01) == bbox.size.Z


def test_rejects_zero_dimension() -> None:
    with pytest.raises(ValueError):
        build_base_connector(width_m=0.0, height_m=0.02)
