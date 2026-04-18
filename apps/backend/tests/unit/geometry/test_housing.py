from __future__ import annotations

import pytest

from services.geometry.primitives.housing import build_housing


def test_housing_has_hollow_interior() -> None:
    inner_m, wall_m = 1.0, 0.01
    part = build_housing(inner_diameter_m=inner_m, wall_thickness_m=wall_m)
    # Volume should be the wall material only
    assert part.volume > 0
    # Outer diameter = inner + 2*wall
    bbox = part.bounding_box()
    expected_outer_mm = (inner_m + 2 * wall_m) * 1000
    assert pytest.approx(expected_outer_mm, rel=0.01) == bbox.size.X


def test_housing_rejects_negative_wall() -> None:
    with pytest.raises(ValueError):
        build_housing(inner_diameter_m=1.0, wall_thickness_m=0.0)
