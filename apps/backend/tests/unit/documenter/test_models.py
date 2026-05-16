"""DocumentRequest + Deliverables model tests."""
from __future__ import annotations

from services.documenter.domain.models import Deliverables, DocumentRequest
from services.explainer.domain.models import NaturalReport
from services.geometry.domain.artifacts import CachedArtifacts, MassProperties
from services.interpreter.domain.intent import DesignIntent, FieldSource, TriStateField
from services.physics.domain.models import AnalysisResult, Verdict


def _intent() -> DesignIntent:
    return DesignIntent(
        type="Flywheel_Rim",
        fields={"rpm": TriStateField(value=3000.0, source=FieldSource.EXTRACTED)},
        composed_of=[],
    )


def _analysis() -> AnalysisResult:
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


def _narrative() -> NaturalReport:
    return NaturalReport(summary="ok", facts_used=["safety_factor"])


def _artifacts() -> CachedArtifacts:
    return CachedArtifacts(
        mass_properties=MassProperties(
            volume_m3=0.012,
            mass_kg=95.5,
            center_of_mass=(0.0, 0.0, 0.025),
            bbox_m=(-0.25, -0.25, 0.0, 0.25, 0.25, 0.05),
        ),
        step_url="https://example.com/step",
        glb_url="https://example.com/glb",
        svg_url="https://example.com/svg",
    )


def test_document_request_carries_all_subsystem_outputs() -> None:
    req = DocumentRequest(
        intent=_intent(),
        analysis_result=_analysis(),
        natural_report=_narrative(),
        geometry_artifacts=_artifacts(),
        session_id="sess-1",
    )
    assert req.intent.type == "Flywheel_Rim"
    assert req.analysis_result.verdict is Verdict.PASS
    assert req.natural_report.summary == "ok"
    assert req.geometry_artifacts.step_url == "https://example.com/step"
    assert req.session_id == "sess-1"


def test_document_request_session_id_optional() -> None:
    req = DocumentRequest(
        intent=_intent(),
        analysis_result=_analysis(),
        natural_report=_narrative(),
        geometry_artifacts=_artifacts(),
    )
    assert req.session_id is None


def test_deliverables_roundtrip() -> None:
    d = Deliverables(
        report_pdf_url="fake://bucket/documents/abc/report.pdf",
        drawing_pdf_url="fake://bucket/documents/abc/drawing.pdf",
        step_url="x",
        glb_url="y",
        svg_url="z",
        cache_hit=False,
        cache_key="abc",
    )
    parsed = Deliverables.model_validate_json(d.model_dump_json())
    assert parsed.cache_key == "abc"
    assert parsed.cache_hit is False
    assert parsed.report_pdf_url.endswith("/report.pdf")


def test_deliverables_cache_hit_flag() -> None:
    d = Deliverables(
        report_pdf_url="r", drawing_pdf_url="d",
        step_url="s", glb_url="g", svg_url="v",
        cache_hit=True, cache_key="abc",
    )
    assert d.cache_hit is True
