"""Visual constants for S5 Documenter PDFs.

Aligned with the Brotea Design System used on the web app so the PDF
reads as part of the same product (electric-violet primary, glow-yellow
accents, dark-eggplant ink on a bone ground).
"""
from __future__ import annotations

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4

PAGE_SIZE = A4                                # ~(595.27, 841.89) pt
MARGIN_PT = 36                                # ~12.7 mm

# ---- Brotea palette ----------------------------------------------------
BROTEA_VIOLET = colors.HexColor("#8081FF")
BROTEA_VIOLET_DEEP = colors.HexColor("#5F60D9")
BROTEA_GLOW = colors.HexColor("#E6FFA9")
BROTEA_GLOW_DEEP = colors.HexColor("#CDE88B")
BROTEA_PINK = colors.HexColor("#FA699F")
BROTEA_EGGPLANT = colors.HexColor("#09092D")
BROTEA_BONE = colors.HexColor("#F3F1EA")
INK = colors.HexColor("#09092D")
INK_MUTED = colors.HexColor("#5F5D55")
RULE = colors.HexColor("#C3BFB4")
SURFACE_SOFT = colors.HexColor("#F1EEE5")

# Legacy aliases (kept so older call sites keep working)
BRAND_PRIMARY = BROTEA_VIOLET
BRAND_ACCENT = BROTEA_GLOW

COLOR_VERDICT: dict[str, colors.Color] = {
    "pass": colors.HexColor("#2BA26B"),
    "warn": colors.HexColor("#E4A126"),
    "fail": colors.HexColor("#E0443E"),
}

# ---- Typography --------------------------------------------------------
FONT_TITLE: tuple[str, int] = ("Helvetica-Bold", 24)
FONT_H1: tuple[str, int] = ("Helvetica-Bold", 13)
FONT_H2: tuple[str, int] = ("Helvetica-Bold", 10)
FONT_BODY: tuple[str, int] = ("Helvetica", 9)
FONT_SMALL: tuple[str, int] = ("Helvetica", 8)
FONT_MONO: tuple[str, int] = ("Courier", 8)
FONT_MONO_BOLD: tuple[str, int] = ("Courier-Bold", 8)
FONT_LABEL: tuple[str, int] = ("Helvetica-Bold", 7)

# ---- Drawing line weights (loosely ISO 128 / ASME Y14.2 inspired) ------
LINE_HEAVY = 0.9      # outlines, borders
LINE_MEDIUM = 0.5     # standard
LINE_THIN = 0.25      # dimensions, hatching
