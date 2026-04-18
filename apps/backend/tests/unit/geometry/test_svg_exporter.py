"""Unit tests for SVG exporter."""
from __future__ import annotations

from pathlib import Path

from services.geometry.exporters.svg import export_svg
from services.geometry.primitives.flywheel_rim import build_flywheel_rim


def test_svg_is_xml(tmp_path: Path) -> None:
    part = build_flywheel_rim(0.5, 0.1, 0.05)
    out = tmp_path / "flywheel.svg"
    export_svg(part, out)
    content = out.read_text(encoding="utf-8")
    assert content.lstrip().startswith("<?xml") or content.lstrip().startswith("<svg")
