"""Visual constants for S5 Documenter PDFs."""
from __future__ import annotations

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4

PAGE_SIZE = A4                                # ~(595.27, 841.89) pt
MARGIN_PT = 50                                # ~18 mm

BRAND_PRIMARY = colors.HexColor("#1A73E8")
BRAND_ACCENT = colors.HexColor("#34A853")

COLOR_VERDICT: dict[str, colors.Color] = {
    "pass": colors.HexColor("#34A853"),
    "warn": colors.HexColor("#F4B400"),
    "fail": colors.HexColor("#DB4437"),
}

FONT_TITLE: tuple[str, int] = ("Helvetica-Bold", 22)
FONT_H1: tuple[str, int] = ("Helvetica-Bold", 14)
FONT_H2: tuple[str, int] = ("Helvetica-Bold", 11)
FONT_BODY: tuple[str, int] = ("Helvetica", 10)
FONT_MONO: tuple[str, int] = ("Courier", 9)
