"""Build the 1-page ISO-style technical drawing PDF using reportlab.

Layout (A4 landscape feels nicer but we keep portrait so it pairs with
the report PDF):

    ┌──────────────────────────────────────────────┐
    │  Border + zone markers (A,B,C / 1,2,3,4)      │
    │  ┌──────────┐  ┌──────────┐                   │
    │  │ TOP      │  │ ISO      │                   │
    │  └──────────┘  └──────────┘                   │
    │  ┌──────────┐  ┌──────────┐                   │
    │  │ FRONT    │  │ SIDE     │                   │
    │  └──────────┘  └──────────┘                   │
    │                                                │
    │  NOTES …                       ┌─────────────┐│
    │                                │ TITLE BLOCK ││
    │                                └─────────────┘│
    └──────────────────────────────────────────────┘
"""
from __future__ import annotations

import io
from datetime import UTC, datetime

from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as canvas_mod

from services.documenter.pdf import theme
from services.documenter.pdf.title_block import (
    TITLE_BLOCK_HEIGHT_MM,
    TITLE_BLOCK_WIDTH_MM,
    derive_doc_number,
    draw_third_angle_symbol,
    draw_title_block,
)
from services.geometry.domain.artifacts import MassProperties
from services.interpreter.domain.intent import DesignIntent
from services.interpreter.domain.materials import MaterialProperties

_PROJECT_NAME = "Gemma 4 Good · MechDesign AI"

_NOTES = [
    "All dimensions in metres unless otherwise noted.",
    "General tolerances per ISO 2768-m (medium).",
    "Surface finish Ra 3.2 µm unless otherwise specified.",
    "Material per Bill of Materials in the engineering report.",
    "First-article inspection required before serial production.",
    "Drawing auto-generated from natural-language intent — verify against report before fabrication.",
]


def build_drawing_pdf(
    *,
    views: dict[str, bytes],
    mass: MassProperties,
    intent: DesignIntent,
    material: MaterialProperties,
    now_utc_iso: str,
    cache_key: str | None = None,
) -> bytes:
    """Return PDF bytes for the 1-page ISO-style technical drawing."""
    buf = io.BytesIO()
    c = canvas_mod.Canvas(buf, pagesize=theme.PAGE_SIZE)
    width, height = theme.PAGE_SIZE
    doc_number = derive_doc_number(cache_key or "00000000")

    _draw_border(c, width, height)

    # View grid — 2 columns × 2 rows in the upper part of the sheet
    grid_left = theme.MARGIN_PT + 4 * mm
    grid_top = height - 22 * mm
    view_w = (width - 2 * theme.MARGIN_PT - 12 * mm) / 2
    view_h = 70 * mm
    gap = 4 * mm

    _draw_view(c, "TOP", views.get("top", b""),
               grid_left, grid_top - view_h, view_w, view_h)
    _draw_view(c, "ISOMETRIC", views.get("iso", b""),
               grid_left + view_w + gap, grid_top - view_h, view_w, view_h)
    _draw_view(c, "FRONT", views.get("front", b""),
               grid_left, grid_top - 2 * view_h - gap, view_w, view_h)
    _draw_view(c, "SIDE", views.get("side", b""),
               grid_left + view_w + gap, grid_top - 2 * view_h - gap, view_w, view_h)

    # Bounding box callouts (below the four-view grid)
    bbox_w = mass.bbox_m[3] - mass.bbox_m[0]
    bbox_h = mass.bbox_m[4] - mass.bbox_m[1]
    bbox_d = mass.bbox_m[5] - mass.bbox_m[2]
    callout_y = grid_top - 2 * view_h - gap - 12 * mm
    c.setFont(*theme.FONT_LABEL)
    c.setFillColor(theme.INK_MUTED)
    c.drawString(grid_left, callout_y, "BOUNDING ENVELOPE")
    c.setFont(*theme.FONT_BODY)
    c.setFillColor(theme.INK)
    c.drawString(grid_left, callout_y - 5 * mm, f"X (width)  = {bbox_w:.3f} m")
    c.drawString(grid_left, callout_y - 10 * mm, f"Y (height) = {bbox_h:.3f} m")
    c.drawString(grid_left, callout_y - 15 * mm, f"Z (depth)  = {bbox_d:.3f} m")

    c.setFont(*theme.FONT_LABEL)
    c.setFillColor(theme.INK_MUTED)
    c.drawString(grid_left + 90 * mm, callout_y, "MASS PROPERTIES")
    c.setFont(*theme.FONT_BODY)
    c.setFillColor(theme.INK)
    c.drawString(grid_left + 90 * mm, callout_y - 5 * mm, f"Mass    = {mass.mass_kg:.2f} kg")
    c.drawString(grid_left + 90 * mm, callout_y - 10 * mm, f"Volume  = {mass.volume_m3:.4f} m³")
    c.drawString(
        grid_left + 90 * mm,
        callout_y - 15 * mm,
        f"COG     = ({mass.center_of_mass[0]:.2f}, {mass.center_of_mass[1]:.2f}, {mass.center_of_mass[2]:.2f})",
    )

    # Notes (top-left of bottom band)
    notes_x = theme.MARGIN_PT + 4 * mm
    notes_top = 70 * mm
    c.setFont(*theme.FONT_LABEL)
    c.setFillColor(theme.INK_MUTED)
    c.drawString(notes_x, notes_top, "GENERAL NOTES")
    c.setFont(*theme.FONT_SMALL)
    c.setFillColor(theme.INK)
    for i, note in enumerate(_NOTES, start=1):
        c.drawString(notes_x, notes_top - 5 * mm - (i - 1) * 4 * mm, f"{i}.  {note}")

    # Third-angle symbol (right of notes)
    sym_x = width / 2 + 10 * mm
    sym_y = 55 * mm
    draw_third_angle_symbol(c, sym_x, sym_y)

    # Title block — bottom-right
    tb_x = width - theme.MARGIN_PT - TITLE_BLOCK_WIDTH_MM * mm
    tb_y = theme.MARGIN_PT
    draw_title_block(
        c,
        tb_x,
        tb_y,
        project=_PROJECT_NAME,
        part_name=intent.type.replace("_", " "),
        material=material.name.replace("_", " "),
        doc_number=doc_number,
        revision="R1",
        scale=f"1:{_auto_scale_denom(mass)}",
        units="m",
        sheet="1/1",
        date=now_utc_iso,
    )

    c.save()
    return buf.getvalue()


def _draw_border(c: canvas_mod.Canvas, width: float, height: float) -> None:
    """Heavy outer border + lighter inner border with zone tick marks."""
    margin = theme.MARGIN_PT
    inner = margin + 3 * mm
    c.setStrokeColor(theme.INK)
    c.setLineWidth(theme.LINE_HEAVY)
    c.rect(margin, margin, width - 2 * margin, height - 2 * margin, stroke=1, fill=0)
    c.setLineWidth(theme.LINE_THIN)
    c.rect(inner, inner, width - 2 * inner, height - 2 * inner, stroke=1, fill=0)

    # Zone markers — letters A,B,C,D top→bottom on left, numbers 1..6 left→right on top
    inner_w = width - 2 * inner
    inner_h = height - 2 * inner
    n_cols = 6
    n_rows = 4
    c.setFont(*theme.FONT_LABEL)
    c.setFillColor(theme.INK_MUTED)
    for i in range(n_cols):
        x = inner + inner_w * (i + 0.5) / n_cols
        c.drawCentredString(x, height - inner + 1.5 * mm, str(i + 1))
        c.drawCentredString(x, inner - 4 * mm, str(i + 1))
    for j in range(n_rows):
        y = inner + inner_h * (n_rows - 1 - j + 0.5) / n_rows
        c.drawCentredString(inner - 3 * mm, y - 1, chr(ord("A") + j))
        c.drawCentredString(width - inner + 3 * mm, y - 1, chr(ord("A") + j))


def _draw_view(
    c: canvas_mod.Canvas,
    label: str,
    svg_bytes: bytes,
    x: float,
    y: float,
    w: float,
    h: float,
) -> None:
    # View frame
    c.setStrokeColor(theme.INK)
    c.setLineWidth(theme.LINE_MEDIUM)
    c.rect(x, y, w, h, stroke=1, fill=0)

    # Label tab (top-left, eggplant background)
    label_w = c.stringWidth(label, "Helvetica-Bold", 7) + 8
    label_h = 10
    c.setFillColor(theme.BROTEA_EGGPLANT)
    c.rect(x, y + h - label_h, label_w, label_h, stroke=0, fill=1)
    c.setFillColor(colors.white)
    c.setFont(*theme.FONT_LABEL)
    c.drawString(x + 4, y + h - 7, label)

    embedded = _try_embed_svg(c, svg_bytes, x + 6, y + 6, w - 12, h - label_h - 8)
    if not embedded:
        c.setFillColor(theme.INK_MUTED)
        c.setFont(*theme.FONT_SMALL)
        c.drawCentredString(x + w / 2, y + h / 2, f"[{label.lower()} view unavailable]")


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


def _auto_scale_denom(mass: MassProperties) -> int:
    longest = max(
        mass.bbox_m[3] - mass.bbox_m[0],
        mass.bbox_m[4] - mass.bbox_m[1],
        mass.bbox_m[5] - mass.bbox_m[2],
        1e-6,
    )
    raw = max(longest / 0.1, 1.0)
    pow10 = 1
    while pow10 * 10 <= raw:
        pow10 *= 10
    return pow10
