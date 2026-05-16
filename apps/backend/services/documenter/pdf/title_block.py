"""ISO-style title block for technical drawings + report cover.

Layout follows the bottom-right placement used in ISO 7200 / ASME Y14.1.
Implemented as a reportlab Table so cell widths can be re-tuned easily.
"""
from __future__ import annotations

from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import Table, TableStyle

from services.documenter.pdf import theme


TITLE_BLOCK_WIDTH_MM = 110
TITLE_BLOCK_HEIGHT_MM = 36


def draw_title_block(
    c: Canvas,
    x: float,
    y: float,
    *,
    project: str,
    part_name: str,
    material: str,
    drawn_by: str = "MechDesign AI",
    checked_by: str = "GEMMA 4",
    approved_by: str = "—",
    doc_number: str,
    revision: str = "R1",
    scale: str = "1:1",
    units: str = "m",
    sheet: str = "1/1",
    date: str,
) -> None:
    """Render the title block with its bottom-left corner at (x, y)."""
    col_label_w = 18 * mm
    col_value_w = (TITLE_BLOCK_WIDTH_MM - 18 * 3) * mm / 3  # 3 value columns
    # Easier: 6 columns × ~18mm each — 3 label/value pairs per row, 4 rows
    data = [
        ["PROJECT", project,                        "DOC. No.", doc_number],
        ["PART",    part_name,                      "REV.",     revision],
        ["MATERIAL", material,                      "SCALE",    scale],
        ["DRAWN",    drawn_by,                      "DATE",     date],
        ["CHECKED",  checked_by,                    "UNITS",    units],
        ["APPROVED", approved_by,                   "SHEET",    sheet],
    ]
    col_widths = [18 * mm, 42 * mm, 16 * mm, 34 * mm]
    t = Table(data, colWidths=col_widths, rowHeights=[6 * mm] * 6, hAlign="LEFT")
    t.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 7),
                ("TEXTCOLOR", (0, 0), (-1, -1), theme.INK),
                ("BACKGROUND", (0, 0), (0, -1), theme.SURFACE_SOFT),
                ("BACKGROUND", (2, 0), (2, -1), theme.SURFACE_SOFT),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 1),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
                ("GRID", (0, 0), (-1, -1), 0.4, theme.INK),
                ("BOX", (0, 0), (-1, -1), theme.LINE_HEAVY, theme.INK),
            ]
        )
    )
    t.wrapOn(c, TITLE_BLOCK_WIDTH_MM * mm, TITLE_BLOCK_HEIGHT_MM * mm)
    t.drawOn(c, x, y)


def draw_third_angle_symbol(c: Canvas, x: float, y: float, size: float = 8 * mm) -> None:
    """Tiny third-angle projection cone-and-disc symbol drawn at (x,y)."""
    # Disc on the left
    cx_disc = x + size * 0.3
    r = size * 0.18
    c.setStrokeColor(theme.INK)
    c.setFillColor(colors.white)
    c.setLineWidth(theme.LINE_MEDIUM)
    c.circle(cx_disc, y, r, stroke=1, fill=0)
    c.circle(cx_disc, y, r * 0.4, stroke=1, fill=0)
    # Cone (triangles) on the right
    cone_x = x + size * 0.7
    h = size * 0.36
    p = c.beginPath()
    p.moveTo(cone_x, y + h / 2)
    p.lineTo(cone_x + size * 0.3, y)
    p.lineTo(cone_x, y - h / 2)
    p.close()
    c.drawPath(p, stroke=1, fill=0)
    # Label
    c.setFont(*theme.FONT_SMALL)
    c.setFillColor(theme.INK_MUTED)
    c.drawCentredString(x + size * 0.5, y - size * 0.45, "ISO E (3rd angle)")


def derive_doc_number(cache_key: str) -> str:
    """Short, stable document number from the cache key prefix."""
    short = cache_key[:8].upper()
    return f"MDA-{short}"
