"""LoadCase derivation tests."""
from __future__ import annotations

import math

import pytest

from services.interpreter.domain.intent import DesignIntent, FieldSource, TriStateField
from services.physics.domain.errors import AnalysisErrorCode, AnalysisException
from services.physics.load_case import derive_load_case


def _make_intent(intent_type: str, fields: dict[str, float | None]) -> DesignIntent:
    ts: dict[str, TriStateField] = {}
    for k, v in fields.items():
        if v is None:
            ts[k] = TriStateField(value=None, source=FieldSource.MISSING)
        else:
            ts[k] = TriStateField(value=v, source=FieldSource.EXTRACTED)
    return DesignIntent(type=intent_type, fields=ts, composed_of=[])


def test_flywheel_load_case_from_rpm() -> None:
    intent = _make_intent(
        "Flywheel_Rim",
        {"rpm": 3000.0, "outer_diameter_m": 0.5, "inner_diameter_m": 0.1, "thickness_m": 0.05},
    )
    lc = derive_load_case(intent)
    assert lc.intent_type == "Flywheel_Rim"
    assert math.isclose(
        lc.values["angular_velocity_rad_s"],
        2 * math.pi * 3000.0 / 60.0,
        rel_tol=1e-9,
    )


def test_flywheel_missing_rpm_raises_missing_load() -> None:
    intent = _make_intent(
        "Flywheel_Rim",
        {"outer_diameter_m": 0.5, "inner_diameter_m": 0.1, "thickness_m": 0.05},
    )
    with pytest.raises(AnalysisException) as ei:
        derive_load_case(intent)
    assert ei.value.error.code is AnalysisErrorCode.MISSING_LOAD_PARAMETER
    assert ei.value.error.field == "rpm"


def test_flywheel_missing_geometry_raises_missing_geometry() -> None:
    intent = _make_intent("Flywheel_Rim", {"rpm": 3000.0})
    with pytest.raises(AnalysisException) as ei:
        derive_load_case(intent)
    assert ei.value.error.code is AnalysisErrorCode.MISSING_GEOMETRY_FIELD
    assert ei.value.error.field in {"outer_diameter_m", "inner_diameter_m", "thickness_m"}


def test_flywheel_negative_rpm_raises_invalid() -> None:
    intent = _make_intent(
        "Flywheel_Rim",
        {"rpm": -10.0, "outer_diameter_m": 0.5, "inner_diameter_m": 0.1, "thickness_m": 0.05},
    )
    with pytest.raises(AnalysisException) as ei:
        derive_load_case(intent)
    assert ei.value.error.code is AnalysisErrorCode.INVALID_LOAD_VALUE


def test_unsupported_intent_type() -> None:
    intent = _make_intent("Shaft", {"diameter_m": 0.05, "length_m": 0.5})
    with pytest.raises(AnalysisException) as ei:
        derive_load_case(intent)
    assert ei.value.error.code is AnalysisErrorCode.UNSUPPORTED_INTENT_TYPE
