from __future__ import annotations

import pytest

from services.geometry.primitives.hinge_panel import build_hinge_panel


def test_hinge_panel_bbox() -> None:
    part = build_hinge_panel(width_m=1.0, height_m=2.0, thickness_m=0.02)
    bbox = part.bounding_box()
    assert pytest.approx(1000.0, rel=0.01) == bbox.size.X
    assert pytest.approx(2000.0, rel=0.01) == bbox.size.Y
    assert pytest.approx(20.0, rel=0.01) == bbox.size.Z


def test_hinge_panel_rejects_negative() -> None:
    with pytest.raises(ValueError):
        build_hinge_panel(width_m=-1.0, height_m=2.0, thickness_m=0.02)
