"""Build the 1-page technical drawing PDF using reportlab."""
from __future__ import annotations

import io

from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as canvas_mod

from services.documenter.pdf import theme
from services.geometry.domain.artifacts import MassProperties
from services.interpreter.domain.intent import DesignIntent
from services.interpreter.domain.materials import MaterialProperties

_PROJECT_NAME = "Gemma 4 Good Hackathon"


def build_drawing_pdf(
    *,
    views: dict[str, bytes],
    mass: MassProperties,
    intent: DesignIntent,
    material: MaterialProperties,
    now_utc_iso: str,
) -> bytes:
    """Return PDF bytes for the 1-page technical drawing."""
    buf = io.BytesIO()
    c = canvas_mod.Canvas(buf, pagesize=theme.PAGE_SIZE)
    width, height = theme.PAGE_SIZE
    c.setFillColor(colors.black)

    _draw_view(c, "Front", views.get("front", b""), theme.MARGIN_PT,
               height - theme.MARGIN_PT - 80 * mm, 80 * mm, 60 * mm)
    _draw_view(c, "Side", views.get("side", b""),
               theme.MARGIN_PT + 90 * mm,
               height - theme.MARGIN_PT - 80 * mm, 80 * mm, 60 * mm)
    _draw_view(c, "Iso", views.get("iso", b""),
               theme.MARGIN_PT,
               height - theme.MARGIN_PT - 170 * mm, 80 * mm, 80 * mm)

    bbox_width = mass.bbox_m[3] - mass.bbox_m[0]
    bbox_height = mass.bbox_m[4] - mass.bbox_m[1]
    bbox_depth = mass.bbox_m[5] - mass.bbox_m[2]

    bbox_x = theme.MARGIN_PT + 90 * mm
    bbox_y = height - theme.MARGIN_PT - 110 * mm
    c.setFont(*theme.FONT_BODY)
    c.drawString(bbox_x, bbox_y, f"Width  = {bbox_width:.3f} m")
    c.drawString(bbox_x, bbox_y - 6 * mm, f"Height = {bbox_height:.3f} m")
    c.drawString(bbox_x, bbox_y - 12 * mm, f"Depth  = {bbox_depth:.3f} m")

    c.setFont(*theme.FONT_BODY)
    note = f"mass = {mass.mass_kg:.1f} kg, vol = {mass.volume_m3:.3f} m3"
    c.drawCentredString(width / 2, theme.MARGIN_PT + 8 * mm, note)

    _draw_title_block(c, intent, material, now_utc_iso, mass)

    c.save()
    return buf.getvalue()


def _draw_view(
    c: canvas_mod.Canvas,
    label: str,
    svg_bytes: bytes,
    x: float,
    y: float,
    w: float,
    h: float,
) -> None:
    c.setStrokeColor(colors.lightgrey)
    c.rect(x, y, w, h, stroke=1, fill=0)
    c.setFillColor(colors.black)
    c.setFont(*theme.FONT_H2)
    c.drawString(x + 3, y + h - 12, label)

    embedded = _try_embed_svg(c, svg_bytes, x + 4, y + 4, w - 8, h - 18)
    if not embedded:
        c.setFont(*theme.FONT_BODY)
        c.drawCentredString(x + w / 2, y + h / 2, "[view]")


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


def _draw_title_block(
    c: canvas_mod.Canvas,
    intent: DesignIntent,
    material: MaterialProperties,
    now_utc_iso: str,
    mass: MassProperties,
) -> None:
    width, _ = theme.PAGE_SIZE
    x = width - theme.MARGIN_PT - 60 * mm
    y = theme.MARGIN_PT
    box_w = 60 * mm
    box_h = 30 * mm
    c.setStrokeColor(colors.black)
    c.rect(x, y, box_w, box_h, stroke=1, fill=0)

    c.setFont(*theme.FONT_BODY)
    lines = [
        f"PROJECT  {_PROJECT_NAME}",
        f"PART     {intent.type}",
        f"MATERIAL {material.name}",
        f"DATE     {now_utc_iso}",
        f"SCALE    1:{_auto_scale_denom(mass)}",
        "UNITS    m",
    ]
    for i, line in enumerate(lines):
        c.drawString(x + 2 * mm, y + box_h - (i + 1) * 4 * mm, line)


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
