"""Reusable Table builders for the engineering report.

These wrap reportlab.platypus.Table with the Brotea palette so call
sites can stay declarative ("here are rows") instead of styling each
cell individually.
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import Table, TableStyle

from services.documenter.pdf import theme


def _base_style(header: bool = True) -> list[tuple[Any, ...]]:
    commands: list[tuple[Any, ...]] = [
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("TEXTCOLOR", (0, 0), (-1, -1), theme.INK),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LINEBELOW", (0, 0), (-1, -1), 0.25, theme.RULE),
        ("ROWBACKGROUNDS", (0, 1 if header else 0), (-1, -1), [colors.white, theme.SURFACE_SOFT]),
    ]
    if header:
        commands.extend(
            [
                ("BACKGROUND", (0, 0), (-1, 0), theme.BROTEA_EGGPLANT),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 8),
                ("ALIGN", (0, 0), (-1, 0), "LEFT"),
            ]
        )
    return commands


def make_table(
    rows: Sequence[Sequence[Any]],
    col_widths: Sequence[float] | None = None,
    *,
    header: bool = True,
    align_right_cols: Sequence[int] = (),
) -> Table:
    """Build a styled Table with the Brotea header bar."""
    t = Table(list(rows), colWidths=col_widths, hAlign="LEFT")
    style = _base_style(header=header)
    for col in align_right_cols:
        style.append(("ALIGN", (col, 1 if header else 0), (col, -1), "RIGHT"))
        style.append(("FONTNAME", (col, 1 if header else 0), (col, -1), "Helvetica"))
    t.setStyle(TableStyle(style))
    return t


def draw_table(c: Canvas, table: Table, x: float, y_top: float, max_width: float) -> float:
    """Render a Table on the canvas with its top edge anchored at `y_top`.

    Returns the y-coordinate of the bottom of the rendered table so the
    caller can keep stacking content below.
    """
    w, h = table.wrapOn(c, max_width, 9999)
    table.drawOn(c, x, y_top - h)
    return y_top - h


def make_kv_table(rows: Sequence[tuple[str, str]], col_widths: Sequence[float] | None = None) -> Table:
    """Two-column key/value table, no header bar."""
    data = [list(r) for r in rows]
    t = Table(data, colWidths=col_widths, hAlign="LEFT")
    t.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                ("TEXTCOLOR", (0, 0), (-1, -1), theme.INK),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("LINEBELOW", (0, 0), (-1, -1), 0.25, theme.RULE),
                ("BACKGROUND", (0, 0), (0, -1), theme.SURFACE_SOFT),
            ]
        )
    )
    return t


def draw_safety_factor_bar(
    c: Canvas,
    x: float,
    y: float,
    width: float,
    height: float,
    safety_factor: float,
    threshold_pass: float = 2.0,
    threshold_warn: float = 1.5,
) -> None:
    """Horizontal gauge showing where the safety factor lands on a 0→4 scale.

    Below threshold_warn → fail (red), below threshold_pass → warn (amber),
    above → pass (green). A black tick marks the actual SF.
    """
    scale_max = max(safety_factor * 1.25, threshold_pass * 2.0, 4.0)
    # Coloured bands behind the gauge
    def _band(start: float, end: float, color: colors.Color) -> None:
        x0 = x + (start / scale_max) * width
        x1 = x + (end / scale_max) * width
        c.setFillColor(color)
        c.rect(x0, y, x1 - x0, height, stroke=0, fill=1)

    _band(0, threshold_warn, theme.COLOR_VERDICT["fail"])
    _band(threshold_warn, threshold_pass, theme.COLOR_VERDICT["warn"])
    _band(threshold_pass, scale_max, theme.COLOR_VERDICT["pass"])

    # Border
    c.setStrokeColor(theme.INK)
    c.setLineWidth(theme.LINE_MEDIUM)
    c.rect(x, y, width, height, stroke=1, fill=0)

    # Threshold markers
    for thresh in (threshold_warn, threshold_pass):
        tx = x + (thresh / scale_max) * width
        c.setStrokeColor(theme.INK)
        c.setLineWidth(theme.LINE_THIN)
        c.line(tx, y - 2, tx, y + height + 2)
        c.setFont(*theme.FONT_SMALL)
        c.setFillColor(theme.INK_MUTED)
        c.drawCentredString(tx, y - 8, f"{thresh:.1f}")

    # Actual SF marker
    sf_clamped = min(max(safety_factor, 0), scale_max)
    mx = x + (sf_clamped / scale_max) * width
    c.setFillColor(theme.INK)
    triangle = c.beginPath()
    triangle.moveTo(mx - 3, y + height + 1)
    triangle.lineTo(mx + 3, y + height + 1)
    triangle.lineTo(mx, y + height - 3)
    triangle.close()
    c.drawPath(triangle, stroke=0, fill=1)

    c.setFont(*theme.FONT_MONO_BOLD)
    c.drawCentredString(mx, y + height + 6, f"SF = {safety_factor:.2f}")
