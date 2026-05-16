"""ExplainerCache tests."""
from __future__ import annotations

import math

from services.explainer.cache import ExplainerCache
from services.explainer.domain.models import NaturalReport
from services.interpreter.domain.intent import DesignIntent, FieldSource, TriStateField
from services.physics.domain.models import AnalysisResult, Verdict


def _intent(rpm: float = 3000.0) -> DesignIntent:
    return DesignIntent(
        type="Flywheel_Rim",
        fields={"rpm": TriStateField(value=rpm, source=FieldSource.EXTRACTED)},
        composed_of=[],
    )


def _result(sf: float = 1.29, stress_pa: float = 1.93e8) -> AnalysisResult:
    return AnalysisResult(
        intent_type="Flywheel_Rim",
        material_name="steel_a36",
        material_yield_mpa=250.0,
        formula="sigma = rho*omega^2*R^2",
        stress_max_pa=stress_pa,
        displacement_max_m=4.8e-4,
        safety_factor=sf,
        verdict=Verdict.WARN if sf < 2.0 else Verdict.PASS,
        inputs={},
    )


def test_get_returns_none_on_miss() -> None:
    cache = ExplainerCache()
    assert cache.get("nonexistent") is None


def test_put_then_get_roundtrip() -> None:
    cache = ExplainerCache()
    report = NaturalReport(summary="ok")
    cache.put("k1", report)
    assert cache.get("k1") is report


def test_key_is_deterministic() -> None:
    intent = _intent()
    result = _result()
    k1 = ExplainerCache.key_for(intent, result)
    k2 = ExplainerCache.key_for(intent, result)
    assert k1 == k2
    assert len(k1) == 16


def test_key_changes_when_safety_factor_changes() -> None:
    intent = _intent()
    k1 = ExplainerCache.key_for(intent, _result(sf=1.29))
    k2 = ExplainerCache.key_for(intent, _result(sf=2.5))
    assert k1 != k2


def test_key_changes_when_intent_field_changes() -> None:
    k1 = ExplainerCache.key_for(_intent(rpm=3000.0), _result())
    k2 = ExplainerCache.key_for(_intent(rpm=4000.0), _result())
    assert k1 != k2


def test_key_handles_infinite_safety_factor() -> None:
    intent = _intent()
    result = _result(sf=math.inf, stress_pa=0.0)
    # Must not raise
    key = ExplainerCache.key_for(intent, result)
    assert isinstance(key, str)
    assert len(key) == 16


def test_clear_empties_cache() -> None:
    cache = ExplainerCache()
    cache.put("k", NaturalReport(summary="x"))
    cache.clear()
    assert cache.get("k") is None
