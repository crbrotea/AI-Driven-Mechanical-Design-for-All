"""Unit tests for STEP exporter."""
from __future__ import annotations

from pathlib import Path

from services.geometry.exporters.step import export_step
from services.geometry.primitives.shaft import build_shaft


def test_step_starts_with_iso_magic(tmp_path: Path) -> None:
    part = build_shaft(0.05, 0.5)
    out = tmp_path / "shaft.step"
    export_step(part, out)
    content = out.read_text(encoding="utf-8")
    assert content.startswith("ISO-10303-21;")


def test_step_is_nonempty(tmp_path: Path) -> None:
    part = build_shaft(0.05, 0.5)
    out = tmp_path / "shaft.step"
    export_step(part, out)
    assert out.stat().st_size > 100
