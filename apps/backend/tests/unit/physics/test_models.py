"""Verdict + classify_verdict tests."""
from __future__ import annotations

import math

import pytest

from services.physics.domain.models import (
    AnalysisResult,
    LoadCase,
    Verdict,
    classify_verdict,
)


@pytest.mark.parametrize(
    "safety_factor, expected",
    [
        (5.0, Verdict.PASS),
        (2.0, Verdict.PASS),
        (1.99, Verdict.WARN),
        (1.5, Verdict.WARN),
        (1.49, Verdict.FAIL),
        (0.5, Verdict.FAIL),
        (math.inf, Verdict.PASS),
    ],
)
def test_classify_verdict(safety_factor: float, expected: Verdict) -> None:
    assert classify_verdict(safety_factor) is expected


def test_load_case_roundtrip() -> None:
    lc = LoadCase(intent_type="Flywheel_Rim", values={"angular_velocity_rad_s": 314.16})
    assert lc.model_dump()["intent_type"] == "Flywheel_Rim"


def test_analysis_result_required_fields() -> None:
    r = AnalysisResult(
        intent_type="Flywheel_Rim",
        material_name="steel_a36",
        material_yield_mpa=250.0,
        formula="σ = ρω²R²",
        stress_max_pa=1.0e8,
        displacement_max_m=1.0e-3,
        safety_factor=2.5,
        verdict=Verdict.PASS,
        inputs={"omega": 314.16},
    )
    assert r.verdict is Verdict.PASS
    assert r.notes is None  # default
