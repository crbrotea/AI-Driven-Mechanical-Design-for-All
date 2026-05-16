"""Build the 5-page engineering report PDF using reportlab."""
from __future__ import annotations

import io
from datetime import UTC, datetime

from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as canvas_mod

from services.documenter.pdf import theme
from services.explainer.domain.models import NaturalReport
from services.geometry.domain.artifacts import CachedArtifacts
from services.interpreter.domain.intent import DesignIntent
from services.interpreter.domain.materials import MaterialProperties
from services.physics.domain.models import AnalysisResult

_VERSION = "S5 Documenter v0.1"

_DERIVATIONS: dict[str, str] = {
    "Flywheel_Rim": (
        "Centrifugal stress on a thin rim spinning at angular velocity omega "
        "is sigma = rho * omega^2 * R^2 where rho is density and R is outer "
        "radius. The result is the maximum tangential stress at the periphery."
    ),
    "Pelton_Runner": (
        "Hydraulic power is rho_w*g*Q*H*eta. Optimal bucket speed is "
        "u = 0.46 * sqrt(2*g*H). Shaft torque follows from T = P/omega and the "
        "shear stress on the shaft is tau = 16T/(pi*d^3)."
    ),
    "Hinge_Panel": (
        "Wind pressure is P = C_p * 0.5 * rho_air * v^2. The panel is modeled "
        "as a cantilever loaded by P; bending stress sigma = 6PL^2/t^2 with L "
        "the cantilever length and t the thickness."
    ),
}


def build_report_pdf(
    *,
    intent: DesignIntent,
    analysis: AnalysisResult,
    narrative: NaturalReport,
    geometry: CachedArtifacts,
    material: MaterialProperties,
    svg_bytes: bytes,
    now_utc_iso: str,
    cache_key: str,
) -> bytes:
    """Return PDF bytes for the 5-page engineering report."""
    buf = io.BytesIO()
    c = canvas_mod.Canvas(buf, pagesize=theme.PAGE_SIZE)
    _draw_cover(c, intent, analysis, now_utc_iso, cache_key)
    c.showPage()
    _draw_intent(c, intent, material)
    c.showPage()
    _draw_geometry(c, geometry, svg_bytes)
    c.showPage()
    _draw_analysis_and_narrative(c, analysis, narrative)
    c.showPage()
    _draw_appendix(c, material, analysis, narrative)
    c.showPage()
    c.save()
    return buf.getvalue()


def _draw_cover(
    c: canvas_mod.Canvas,
    intent: DesignIntent,
    analysis: AnalysisResult,
    now_utc_iso: str,
    cache_key: str,
) -> None:
    width, height = theme.PAGE_SIZE
    c.setFillColor(theme.BRAND_PRIMARY)
    c.rect(0, height - 40 * mm, width, 40 * mm, stroke=0, fill=1)

    c.setFont(*theme.FONT_TITLE)
    c.setFillColor(colors.white)
    c.drawString(theme.MARGIN_PT, height - 28 * mm, "Mechanical Design Report")

    c.setFillColor(colors.black)
    c.setFont(*theme.FONT_H1)
    c.drawString(theme.MARGIN_PT, height - 60 * mm, intent.type)

    c.setFont(*theme.FONT_BODY)
    c.drawString(theme.MARGIN_PT, height - 70 * mm, f"Date: {now_utc_iso}")

    c.setFont(*theme.FONT_MONO)
    c.drawString(theme.MARGIN_PT, theme.MARGIN_PT, f"cache_key: {cache_key}")

    verdict = analysis.verdict.value
    badge_color = theme.COLOR_VERDICT.get(verdict, colors.grey)
    badge_x = width - theme.MARGIN_PT - 60 * mm
    badge_y = theme.MARGIN_PT
    c.setFillColor(badge_color)
    c.roundRect(badge_x, badge_y, 60 * mm, 18 * mm, 4, stroke=0, fill=1)
    c.setFillColor(colors.white)
    c.setFont(*theme.FONT_H1)
    c.drawCentredString(badge_x + 30 * mm, badge_y + 6 * mm, verdict.upper())


def _draw_intent(
    c: canvas_mod.Canvas,
    intent: DesignIntent,
    material: MaterialProperties,
) -> None:
    _, height = theme.PAGE_SIZE
    y = height - theme.MARGIN_PT
    c.setFillColor(colors.black)
    c.setFont(*theme.FONT_H1)
    c.drawString(theme.MARGIN_PT, y, "Design Intent")
    y -= 10 * mm

    c.setFont(*theme.FONT_BODY)
    for name, field in sorted(intent.fields.items()):
        if field.value is None:
            continue
        line = f"{name} = {field.value}  [{field.source.value}]"
        c.drawString(theme.MARGIN_PT, y, line)
        y -= 6 * mm

    y -= 4 * mm
    c.setFont(*theme.FONT_H1)
    c.drawString(theme.MARGIN_PT, y, "Material")
    y -= 8 * mm
    c.setFont(*theme.FONT_BODY)
    rows = [
        ("name", material.name),
        ("density (kg/m3)", f"{material.density_kg_m3:.0f}"),
        ("young_modulus (GPa)", f"{material.young_modulus_gpa:.1f}"),
        ("yield_strength (MPa)", f"{material.yield_strength_mpa:.1f}"),
        ("category", material.category),
    ]
    for label, value in rows:
        c.drawString(theme.MARGIN_PT, y, f"{label}: {value}")
        y -= 6 * mm


def _draw_geometry(
    c: canvas_mod.Canvas,
    geometry: CachedArtifacts,
    svg_bytes: bytes,
) -> None:
    _, height = theme.PAGE_SIZE
    y = height - theme.MARGIN_PT
    c.setFillColor(colors.black)
    c.setFont(*theme.FONT_H1)
    c.drawString(theme.MARGIN_PT, y, "Geometry")
    y -= 10 * mm

    m = geometry.mass_properties
    c.setFont(*theme.FONT_BODY)
    rows = [
        ("mass (kg)", f"{m.mass_kg:.2f}"),
        ("volume (m3)", f"{m.volume_m3:.4f}"),
        (
            "center_of_mass (m)",
            f"({m.center_of_mass[0]:.3f}, {m.center_of_mass[1]:.3f}, {m.center_of_mass[2]:.3f})",
        ),
        (
            "bbox_min (m)",
            f"({m.bbox_m[0]:.3f}, {m.bbox_m[1]:.3f}, {m.bbox_m[2]:.3f})",
        ),
        (
            "bbox_max (m)",
            f"({m.bbox_m[3]:.3f}, {m.bbox_m[4]:.3f}, {m.bbox_m[5]:.3f})",
        ),
    ]
    for label, value in rows:
        c.drawString(theme.MARGIN_PT, y, f"{label}: {value}")
        y -= 6 * mm

    y -= 6 * mm
    c.setFont(*theme.FONT_H2)
    c.drawString(theme.MARGIN_PT, y, "Section view")
    y -= 6 * mm
    c.setFont(*theme.FONT_BODY)
    embedded = _try_embed_svg(
        c, svg_bytes, theme.MARGIN_PT, y - 100 * mm, 100 * mm, 100 * mm
    )
    if not embedded:
        c.drawString(
            theme.MARGIN_PT,
            y - 6 * mm,
            f"[section view available at {geometry.svg_url}]",
        )


def _try_embed_svg(
    c: canvas_mod.Canvas,
    svg_bytes: bytes,
    x: float,
    y: float,
    w: float,
    h: float,
) -> bool:
    try:
        from reportlab.graphics import renderPDF
        from svglib.svglib import svg2rlg  # type: ignore[import-not-found]
    except ImportError:
        return False
    try:
        drawing = svg2rlg(io.BytesIO(svg_bytes))
        if drawing is None:
            return False
        scale_x = w / drawing.width if drawing.width else 1.0
        scale_y = h / drawing.height if drawing.height else 1.0
        scale = min(scale_x, scale_y)
        drawing.scale(scale, scale)
        renderPDF.draw(drawing, c, x, y)
        return True
    except Exception:
        return False


def _draw_analysis_and_narrative(
    c: canvas_mod.Canvas,
    analysis: AnalysisResult,
    narrative: NaturalReport,
) -> None:
    width, height = theme.PAGE_SIZE
    y = height - theme.MARGIN_PT
    c.setFillColor(colors.black)
    c.setFont(*theme.FONT_H1)
    c.drawString(theme.MARGIN_PT, y, "Structural Analysis")
    y -= 10 * mm

    c.setFont(*theme.FONT_MONO)
    c.drawString(theme.MARGIN_PT, y, f"Formula: {analysis.formula}")
    y -= 6 * mm

    c.setFont(*theme.FONT_BODY)
    rows = [
        ("Stress max (MPa)", f"{analysis.stress_max_pa / 1e6:.2f}"),
        ("Yield (MPa)", f"{analysis.material_yield_mpa:.1f}"),
        ("Displacement max (mm)", f"{analysis.displacement_max_m * 1000:.3f}"),
        ("Safety factor", f"{analysis.safety_factor:.2f}"),
    ]
    for label, value in rows:
        c.drawString(theme.MARGIN_PT, y, f"{label}: {value}")
        y -= 6 * mm

    verdict = analysis.verdict.value
    badge_color = theme.COLOR_VERDICT.get(verdict, colors.grey)
    c.setFillColor(badge_color)
    c.roundRect(
        width - theme.MARGIN_PT - 30 * mm, y, 30 * mm, 8 * mm, 2, stroke=0, fill=1
    )
    c.setFillColor(colors.white)
    c.setFont(*theme.FONT_H2)
    c.drawCentredString(
        width - theme.MARGIN_PT - 15 * mm, y + 2 * mm, verdict.upper()
    )
    y -= 14 * mm
    c.setFillColor(colors.black)

    c.setFont(*theme.FONT_H1)
    c.drawString(theme.MARGIN_PT, y, "Engineering Narrative")
    y -= 8 * mm

    c.setFont(*theme.FONT_H2)
    c.drawString(theme.MARGIN_PT, y, "Summary")
    y -= 6 * mm
    c.setFont(*theme.FONT_BODY)
    y = _draw_wrapped(
        c, narrative.summary, theme.MARGIN_PT, y, width - 2 * theme.MARGIN_PT
    )

    for heading, items in (
        ("Risks", narrative.risks),
        ("Suggestions", narrative.suggestions),
        ("Analogies", narrative.analogies),
    ):
        y -= 4 * mm
        c.setFont(*theme.FONT_H2)
        c.drawString(theme.MARGIN_PT, y, heading)
        y -= 6 * mm
        c.setFont(*theme.FONT_BODY)
        for item in items:
            c.drawString(theme.MARGIN_PT, y, f"- {item}")
            y -= 5 * mm

    c.setFont(*theme.FONT_MONO)
    c.drawString(
        theme.MARGIN_PT,
        theme.MARGIN_PT,
        "Facts cited: " + ", ".join(narrative.facts_used),
    )


def _draw_appendix(
    c: canvas_mod.Canvas,
    material: MaterialProperties,
    analysis: AnalysisResult,
    narrative: NaturalReport,
) -> None:
    width, height = theme.PAGE_SIZE
    y = height - theme.MARGIN_PT
    c.setFillColor(colors.black)
    c.setFont(*theme.FONT_H1)
    c.drawString(theme.MARGIN_PT, y, "Technical Appendix")
    y -= 10 * mm

    c.setFont(*theme.FONT_H2)
    c.drawString(theme.MARGIN_PT, y, "Material Properties (full)")
    y -= 8 * mm
    c.setFont(*theme.FONT_BODY)
    for label, value in [
        ("density_kg_m3", f"{material.density_kg_m3:.0f}"),
        ("young_modulus_gpa", f"{material.young_modulus_gpa:.1f}"),
        ("yield_strength_mpa", f"{material.yield_strength_mpa:.1f}"),
        ("ultimate_tensile_strength_mpa", f"{material.ultimate_tensile_strength_mpa:.1f}"),
        ("thermal_conductivity_w_m_k", f"{material.thermal_conductivity_w_m_k:.2f}"),
        ("max_service_temperature_c", f"{material.max_service_temperature_c:.0f}"),
        ("relative_cost_index", f"{material.relative_cost_index:.2f}"),
        ("sustainability_score", f"{material.sustainability_score:.2f}"),
    ]:
        c.drawString(theme.MARGIN_PT, y, f"{label}: {value}")
        y -= 6 * mm

    y -= 4 * mm
    c.setFont(*theme.FONT_H2)
    c.drawString(theme.MARGIN_PT, y, "Assumptions and Notes")
    y -= 6 * mm
    c.setFont(*theme.FONT_BODY)
    notes = analysis.notes or "(no notes recorded)"
    for sentence in notes.split(". "):
        if not sentence.strip():
            continue
        c.drawString(theme.MARGIN_PT, y, f"- {sentence.strip().rstrip('.')}")
        y -= 5 * mm
    c.drawString(
        theme.MARGIN_PT,
        y,
        f"- FACTS used for narrative: {', '.join(narrative.facts_used)}",
    )
    y -= 8 * mm

    c.setFont(*theme.FONT_H2)
    c.drawString(theme.MARGIN_PT, y, "Formula Derivation")
    y -= 6 * mm
    c.setFont(*theme.FONT_MONO)
    c.drawString(theme.MARGIN_PT, y, analysis.formula)
    y -= 8 * mm
    c.setFont(*theme.FONT_BODY)
    derivation = _DERIVATIONS.get(
        analysis.intent_type,
        "(derivation reference: see docs/superpowers/specs/2026-05-16-s3-physics-design.md)",
    )
    y = _draw_wrapped(
        c, derivation, theme.MARGIN_PT, y, width - 2 * theme.MARGIN_PT
    )

    footer = (
        f"{_VERSION} -- generated UTC "
        f"{datetime.now(tz=UTC).strftime('%Y-%m-%d %H:%M')}"
    )
    c.setFont(*theme.FONT_MONO)
    c.drawString(theme.MARGIN_PT, theme.MARGIN_PT, footer)


def _draw_wrapped(
    c: canvas_mod.Canvas,
    text: str,
    x: float,
    y: float,
    max_width: float,
    line_height: float = 12.0,
) -> float:
    """Naive word-wrap: returns new y."""
    words = text.split()
    if not words:
        return y
    line = ""
    for w in words:
        candidate = (line + " " + w).strip()
        if c.stringWidth(candidate, "Helvetica", 10) <= max_width:
            line = candidate
        else:
            c.drawString(x, y, line)
            y -= line_height
            line = w
    if line:
        c.drawString(x, y, line)
        y -= line_height
    return y
