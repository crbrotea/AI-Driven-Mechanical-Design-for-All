"""Unit tests for Pelton_Runner builder (simplified)."""
from __future__ import annotations

import pytest

from services.geometry.primitives.pelton_runner import build_pelton_runner


def test_bbox_matches_runner_diameter() -> None:
    part = build_pelton_runner(runner_diameter_m=0.8, bucket_count=20)
    bbox = part.bounding_box()
    assert pytest.approx(800.0, rel=0.02) == bbox.size.X


def test_volume_positive() -> None:
    part = build_pelton_runner(runner_diameter_m=0.8, bucket_count=20)
    assert part.volume > 0


def test_rejects_invalid_bucket_count() -> None:
    with pytest.raises(ValueError):
        build_pelton_runner(runner_diameter_m=0.8, bucket_count=5)
    with pytest.raises(ValueError):
        build_pelton_runner(runner_diameter_m=0.8, bucket_count=50)


def test_rejects_zero_diameter() -> None:
    with pytest.raises(ValueError):
        build_pelton_runner(runner_diameter_m=0.0, bucket_count=20)


def test_deterministic() -> None:
    p1 = build_pelton_runner(0.8, 20)
    p2 = build_pelton_runner(0.8, 20)
    assert p1.volume == pytest.approx(p2.volume, rel=1e-6)
