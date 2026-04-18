from __future__ import annotations

import pytest

from services.geometry.primitives.mounting_frame import build_mounting_frame


def test_mounting_frame_bbox() -> None:
    part = build_mounting_frame(length_m=1.0, width_m=0.6, height_m=0.1)
    bbox = part.bounding_box()
    assert pytest.approx(1000.0, rel=0.01) == bbox.size.X
    assert pytest.approx(600.0, rel=0.01) == bbox.size.Y
    assert pytest.approx(100.0, rel=0.01) == bbox.size.Z


def test_mounting_frame_rejects_zero_dim() -> None:
    with pytest.raises(ValueError):
        build_mounting_frame(length_m=0.0, width_m=0.6, height_m=0.1)
