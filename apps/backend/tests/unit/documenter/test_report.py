"""build_report_pdf tests."""
from __future__ import annotations

import io

import pypdf

from services.documenter.pdf.report import build_report_pdf
from services.explainer.domain.models import NaturalReport
from services.geometry.domain.artifacts import CachedArtifacts, MassProperties
from services.interpreter.domain.intent import DesignIntent, FieldSource, TriStateField
from services.interpreter.domain.materials import MaterialProperties
from services.physics.domain.models import AnalysisResult, Verdict


def _read(pdf: bytes) -> pypdf.PdfReader:
    return pypdf.PdfReader(io.BytesIO(pdf))


def _all_text(pdf: bytes) -> str:
    reader = _read(pdf)
    return "\n".join((p.extract_text() or "") for p in reader.pages)


_STEEL = MaterialProperties(
    name="steel_a36",
    display_name="Steel A36",
    category="metal",
    density_kg_m3=7850.0,
    young_modulus_gpa=200.0,
    yield_strength_mpa=250.0,
    ultimate_tensile_strength_mpa=400.0,
    thermal_conductivity_w_m_k=51.0,
    max_service_temperature_c=400.0,
    relative_cost_index=1.0,
    sustainability_score=0.5,
)


def _intent() -> DesignIntent:
    return DesignIntent(
        type="Flywheel_Rim",
        fields={
            "outer_diameter_m": TriStateField(value=0.5, source=FieldSource.EXTRACTED),
            "rpm": TriStateField(value=3000.0, source=FieldSource.EXTRACTED),
        },
        composed_of=[],
    )


def _analysis() -> AnalysisResult:
    return AnalysisResult(
        intent_type="Flywheel_Rim",
        material_name="steel_a36",
        material_yield_mpa=250.0,
        formula="sigma = rho*omega^2*R^2",
        stress_max_pa=1.937e8,
        displacement_max_m=4.84e-4,
        safety_factor=1.29,
        verdict=Verdict.WARN,
        inputs={"angular_velocity_rad_s": 314.159},
    )


def _narrative() -> NaturalReport:
    return NaturalReport(
        summary="Near-yield at 3000 rpm; design hits the energy target.",
        risks=["Stress is 77% of yield."],
        suggestions=["Verify rim with FEA."],
        analogies=["Like a sprinter at top speed."],
        facts_used=["stress_max_mpa", "safety_factor", "material_yield_mpa"],
    )


def _geometry() -> CachedArtifacts:
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


_SVG_BYTES = (
    b'<?xml version="1.0"?>'
    b'<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"/>'
)


def test_report_pdf_has_pdf_magic_bytes() -> None:
    pdf = build_report_pdf(
        intent=_intent(),
        analysis=_analysis(),
        narrative=_narrative(),
        geometry=_geometry(),
        material=_STEEL,
        svg_bytes=_SVG_BYTES,
        now_utc_iso="2026-05-16T12:00:00Z",
        cache_key="abc123",
    )
    assert pdf.startswith(b"%PDF-")


def test_report_pdf_has_five_pages() -> None:
    pdf = build_report_pdf(
        intent=_intent(), analysis=_analysis(), narrative=_narrative(),
        geometry=_geometry(), material=_STEEL, svg_bytes=_SVG_BYTES,
        now_utc_iso="2026-05-16T12:00:00Z", cache_key="abc123",
    )
    assert len(_read(pdf).pages) == 5


def test_report_pdf_contains_intent_type() -> None:
    pdf = build_report_pdf(
        intent=_intent(), analysis=_analysis(), narrative=_narrative(),
        geometry=_geometry(), material=_STEEL, svg_bytes=_SVG_BYTES,
        now_utc_iso="2026-05-16T12:00:00Z", cache_key="abc123",
    )
    assert "Flywheel_Rim" in _all_text(pdf)


def test_report_pdf_contains_verdict_label() -> None:
    pdf = build_report_pdf(
        intent=_intent(), analysis=_analysis(), narrative=_narrative(),
        geometry=_geometry(), material=_STEEL, svg_bytes=_SVG_BYTES,
        now_utc_iso="2026-05-16T12:00:00Z", cache_key="abc123",
    )
    text = _all_text(pdf).upper()
    assert "WARN" in text


def test_report_pdf_contains_formula() -> None:
    pdf = build_report_pdf(
        intent=_intent(), analysis=_analysis(), narrative=_narrative(),
        geometry=_geometry(), material=_STEEL, svg_bytes=_SVG_BYTES,
        now_utc_iso="2026-05-16T12:00:00Z", cache_key="abc123",
    )
    assert "sigma = rho*omega^2*R^2" in _all_text(pdf)


def test_report_pdf_contains_safety_factor_value() -> None:
    pdf = build_report_pdf(
        intent=_intent(), analysis=_analysis(), narrative=_narrative(),
        geometry=_geometry(), material=_STEEL, svg_bytes=_SVG_BYTES,
        now_utc_iso="2026-05-16T12:00:00Z", cache_key="abc123",
    )
    assert "1.29" in _all_text(pdf)


def test_report_pdf_contains_material_name() -> None:
    pdf = build_report_pdf(
        intent=_intent(), analysis=_analysis(), narrative=_narrative(),
        geometry=_geometry(), material=_STEEL, svg_bytes=_SVG_BYTES,
        now_utc_iso="2026-05-16T12:00:00Z", cache_key="abc123",
    )
    assert "steel_a36" in _all_text(pdf)


def test_report_pdf_contains_facts_used_labels() -> None:
    pdf = build_report_pdf(
        intent=_intent(), analysis=_analysis(), narrative=_narrative(),
        geometry=_geometry(), material=_STEEL, svg_bytes=_SVG_BYTES,
        now_utc_iso="2026-05-16T12:00:00Z", cache_key="abc123",
    )
    text = _all_text(pdf)
    for label in ("stress_max_mpa", "safety_factor", "material_yield_mpa"):
        assert label in text, f"facts label missing in PDF: {label}"
