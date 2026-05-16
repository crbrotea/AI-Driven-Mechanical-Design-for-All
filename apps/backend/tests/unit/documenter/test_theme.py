"""Theme constants tests."""
from __future__ import annotations

from services.documenter.pdf import theme


def test_page_size_is_a4() -> None:
    width, height = theme.PAGE_SIZE
    assert 590 < width < 600
    assert 840 < height < 845


def test_verdict_color_map_covers_all_verdicts() -> None:
    assert "pass" in theme.COLOR_VERDICT
    assert "warn" in theme.COLOR_VERDICT
    assert "fail" in theme.COLOR_VERDICT


def test_fonts_are_tuples_of_name_and_size() -> None:
    for font in (theme.FONT_TITLE, theme.FONT_H1, theme.FONT_H2, theme.FONT_BODY, theme.FONT_MONO):
        assert isinstance(font, tuple)
        assert len(font) == 2
        assert isinstance(font[0], str)
        assert isinstance(font[1], int | float)
