"""build_drawing_pdf tests."""
from __future__ import annotations

import io

import pypdf

from services.documenter.pdf.drawing import build_drawing_pdf
from services.geometry.domain.artifacts import MassProperties
from services.interpreter.domain.intent import DesignIntent, FieldSource, TriStateField
from services.interpreter.domain.materials import MaterialProperties


def _read_text(pdf: bytes) -> str:
    reader = pypdf.PdfReader(io.BytesIO(pdf))
    return "\n".join((p.extract_text() or "") for p in reader.pages)


def _page_count(pdf: bytes) -> int:
    return len(pypdf.PdfReader(io.BytesIO(pdf)).pages)


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
        fields={"outer_diameter_m": TriStateField(value=0.5, source=FieldSource.EXTRACTED)},
        composed_of=[],
    )


_MASS = MassProperties(
    volume_m3=0.012,
    mass_kg=95.5,
    center_of_mass=(0.0, 0.0, 0.025),
    bbox_m=(-0.25, -0.25, 0.0, 0.25, 0.25, 0.05),
)

_SVG = (
    b'<?xml version="1.0"?>'
    b'<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"/>'
)
_VIEWS = {"front": _SVG, "side": _SVG, "iso": _SVG}


def test_drawing_pdf_magic_bytes_and_one_page() -> None:
    pdf = build_drawing_pdf(
        views=_VIEWS, mass=_MASS, intent=_intent(),
        material=_STEEL, now_utc_iso="2026-05-16T12:00:00Z",
    )
    assert pdf.startswith(b"%PDF-")
    assert _page_count(pdf) == 1


def test_drawing_pdf_contains_title_block_fields() -> None:
    pdf = build_drawing_pdf(
        views=_VIEWS, mass=_MASS, intent=_intent(),
        material=_STEEL, now_utc_iso="2026-05-16T12:00:00Z",
    )
    text = _read_text(pdf)
    assert "Flywheel_Rim" in text
    assert "steel_a36" in text


def test_drawing_pdf_contains_bbox_labels() -> None:
    pdf = build_drawing_pdf(
        views=_VIEWS, mass=_MASS, intent=_intent(),
        material=_STEEL, now_utc_iso="2026-05-16T12:00:00Z",
    )
    text = _read_text(pdf)
    assert "Width" in text
    assert "Height" in text
    assert "Depth" in text


def test_drawing_pdf_contains_mass_note() -> None:
    pdf = build_drawing_pdf(
        views=_VIEWS, mass=_MASS, intent=_intent(),
        material=_STEEL, now_utc_iso="2026-05-16T12:00:00Z",
    )
    text = _read_text(pdf)
    assert "mass" in text.lower()
    assert "95.5" in text


def test_drawing_pdf_contains_view_labels() -> None:
    pdf = build_drawing_pdf(
        views=_VIEWS, mass=_MASS, intent=_intent(),
        material=_STEEL, now_utc_iso="2026-05-16T12:00:00Z",
    )
    text = _read_text(pdf).lower()
    assert "front" in text
    assert "side" in text
    assert "iso" in text
