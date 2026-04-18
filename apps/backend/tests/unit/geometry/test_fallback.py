"""Unit tests for demo fallback."""
from __future__ import annotations

from pathlib import Path

from services.geometry.domain.artifacts import MassProperties
from services.geometry.fallback import (
    DEMO_INTENT_HASHES,
    lookup_demo_fallback,
)


async def test_fallback_returns_none_for_unknown_hash(tmp_path: Path) -> None:
    result = await lookup_demo_fallback("unknown_hash", base_dir=tmp_path)
    assert result is None


async def test_fallback_returns_none_if_directory_missing(tmp_path: Path) -> None:
    known = next(iter(DEMO_INTENT_HASHES.values()))
    # No directory exists
    result = await lookup_demo_fallback(known, base_dir=tmp_path)
    assert result is None


async def test_fallback_returns_cached_artifacts_if_present(tmp_path: Path) -> None:
    known = next(iter(DEMO_INTENT_HASHES.values()))
    dir_ = tmp_path / known
    dir_.mkdir()
    (dir_ / "geometry.step").write_bytes(b"ISO-10303-21;")
    (dir_ / "geometry.glb").write_bytes(b"glTF")
    (dir_ / "section.svg").write_bytes(b"<svg></svg>")
    mass = MassProperties(
        volume_m3=0.01, mass_kg=50.0,
        center_of_mass=(0, 0, 0),
        bbox_m=(0, 0, 0, 1, 1, 1),
    )
    (dir_ / "mass.json").write_text(mass.model_dump_json())

    result = await lookup_demo_fallback(known, base_dir=tmp_path)
    assert result is not None
    assert result.mass_properties.mass_kg == 50.0
