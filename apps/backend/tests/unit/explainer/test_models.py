"""NaturalReport + ExplainRequest tests."""
from __future__ import annotations

from services.explainer.domain.models import ExplainRequest, NaturalReport
from services.interpreter.domain.intent import DesignIntent, FieldSource, TriStateField
from services.physics.domain.models import AnalysisResult, Verdict


def _intent() -> DesignIntent:
    return DesignIntent(
        type="Flywheel_Rim",
        fields={"rpm": TriStateField(value=3000.0, source=FieldSource.EXTRACTED)},
        composed_of=[],
    )


def _result() -> AnalysisResult:
    return AnalysisResult(
        intent_type="Flywheel_Rim",
        material_name="steel_a36",
        material_yield_mpa=250.0,
        formula="sigma = rho*omega^2*R^2",
        stress_max_pa=1.0e8,
        displacement_max_m=1.0e-3,
        safety_factor=2.5,
        verdict=Verdict.PASS,
        inputs={},
    )


def test_natural_report_roundtrip() -> None:
    report = NaturalReport(
        summary="A solid design at 3000 rpm.",
        risks=["Stress near 40% of yield."],
        suggestions=["Consider increasing radius."],
        analogies=["Like a wheel that never tires."],
        facts_used=["safety_factor", "stress_max_mpa"],
    )
    parsed = NaturalReport.model_validate_json(report.model_dump_json())
    assert parsed.summary == report.summary
    assert parsed.facts_used == ["safety_factor", "stress_max_mpa"]


def test_natural_report_defaults() -> None:
    report = NaturalReport(summary="x")
    assert report.risks == []
    assert report.suggestions == []
    assert report.analogies == []
    assert report.facts_used == []


def test_explain_request_accepts_intent_and_analysis() -> None:
    req = ExplainRequest(intent=_intent(), analysis_result=_result(), session_id="abc")
    assert req.intent.type == "Flywheel_Rim"
    assert req.analysis_result.verdict is Verdict.PASS
    assert req.session_id == "abc"


def test_explain_request_session_id_optional() -> None:
    req = ExplainRequest(intent=_intent(), analysis_result=_result())
    assert req.session_id is None
