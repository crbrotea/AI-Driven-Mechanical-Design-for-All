"""Unit tests for GLB exporter."""
from __future__ import annotations

from pathlib import Path

from services.geometry.exporters.glb import export_glb
from services.geometry.primitives.shaft import build_shaft


def test_glb_starts_with_gltf_magic(tmp_path: Path) -> None:
    part = build_shaft(0.05, 0.5)
    out = tmp_path / "shaft.glb"
    export_glb(part, out)
    header = out.read_bytes()[:4]
    assert header == b"glTF"


def test_glb_is_nonempty(tmp_path: Path) -> None:
    part = build_shaft(0.05, 0.5)
    out = tmp_path / "shaft.glb"
    export_glb(part, out)
    assert out.stat().st_size > 100
