"""DocumenterCache tests."""
from __future__ import annotations

import math

from services.documenter.cache import DocumenterCache
from services.documenter.domain.models import Deliverables
from services.explainer.domain.models import NaturalReport
from services.interpreter.domain.intent import DesignIntent, FieldSource, TriStateField
from services.physics.domain.models import AnalysisResult, Verdict


def _intent(rpm: float = 3000.0) -> DesignIntent:
    return DesignIntent(
        type="Flywheel_Rim",
        fields={"rpm": TriStateField(value=rpm, source=FieldSource.EXTRACTED)},
        composed_of=[],
    )


def _analysis(sf: float = 1.29, stress: float = 1.93e8) -> AnalysisResult:
    return AnalysisResult(
        intent_type="Flywheel_Rim",
        material_name="steel_a36",
        material_yield_mpa=250.0,
        formula="sigma = rho*omega^2*R^2",
        stress_max_pa=stress,
        displacement_max_m=4.8e-4,
        safety_factor=sf,
        verdict=Verdict.WARN if sf < 2.0 else Verdict.PASS,
        inputs={},
    )


def _narrative(summary: str = "ok", facts: list[str] | None = None) -> NaturalReport:
    return NaturalReport(summary=summary, facts_used=facts or [])


def _deliv(key: str = "k1") -> Deliverables:
    return Deliverables(
        report_pdf_url="r", drawing_pdf_url="d",
        step_url="s", glb_url="g", svg_url="v",
        cache_hit=False, cache_key=key,
    )


def test_get_returns_none_on_miss() -> None:
    cache = DocumenterCache()
    assert cache.get("missing") is None


def test_put_then_get_roundtrip() -> None:
    cache = DocumenterCache()
    d = _deliv()
    cache.put("k1", d)
    assert cache.get("k1") is d


def test_key_is_deterministic_and_16_chars() -> None:
    k1 = DocumenterCache.key_for(_intent(), _analysis(), _narrative())
    k2 = DocumenterCache.key_for(_intent(), _analysis(), _narrative())
    assert k1 == k2
    assert len(k1) == 16


def test_key_changes_when_intent_field_changes() -> None:
    k1 = DocumenterCache.key_for(_intent(rpm=3000.0), _analysis(), _narrative())
    k2 = DocumenterCache.key_for(_intent(rpm=4000.0), _analysis(), _narrative())
    assert k1 != k2


def test_key_changes_when_safety_factor_changes() -> None:
    k1 = DocumenterCache.key_for(_intent(), _analysis(sf=1.29), _narrative())
    k2 = DocumenterCache.key_for(_intent(), _analysis(sf=2.5), _narrative())
    assert k1 != k2


def test_key_changes_when_narrative_summary_changes() -> None:
    k1 = DocumenterCache.key_for(_intent(), _analysis(), _narrative(summary="A"))
    k2 = DocumenterCache.key_for(_intent(), _analysis(), _narrative(summary="B"))
    assert k1 != k2


def test_key_handles_infinite_safety_factor() -> None:
    key = DocumenterCache.key_for(_intent(), _analysis(sf=math.inf, stress=0.0), _narrative())
    assert isinstance(key, str)
    assert len(key) == 16


def test_clear_empties_cache() -> None:
    cache = DocumenterCache()
    cache.put("k", _deliv())
    cache.clear()
    assert cache.get("k") is None
