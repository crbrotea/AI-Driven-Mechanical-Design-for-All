"""Unit tests for artifact domain models."""
from __future__ import annotations

from services.geometry.domain.artifacts import (
    BuiltArtifacts,
    CachedArtifacts,
    MassProperties,
)


def test_mass_properties_roundtrip() -> None:
    mass = MassProperties(
        volume_m3=0.00942,
        mass_kg=74.0,
        center_of_mass=(0.0, 0.0, 0.025),
        bbox_m=(-0.25, -0.25, 0.0, 0.25, 0.25, 0.05),
    )
    data = mass.model_dump()
    restored = MassProperties.model_validate(data)
    assert restored == mass


def test_built_artifacts_carries_bytes() -> None:
    mass = MassProperties(
        volume_m3=0.01,
        mass_kg=78.5,
        center_of_mass=(0.0, 0.0, 0.025),
        bbox_m=(0.0, 0.0, 0.0, 0.5, 0.5, 0.05),
    )
    artifacts = BuiltArtifacts(
        step_bytes=b"ISO-10303-21;",
        glb_bytes=b"glTF\x02\x00\x00\x00",
        svg_bytes=b"<svg></svg>",
        mass=mass,
    )
    assert artifacts.step_bytes.startswith(b"ISO")
    assert artifacts.mass.mass_kg == 78.5


def test_cached_artifacts_carries_urls() -> None:
    mass = MassProperties(
        volume_m3=0.01, mass_kg=78.5,
        center_of_mass=(0.0, 0.0, 0.0),
        bbox_m=(0.0, 0.0, 0.0, 0.1, 0.1, 0.1),
    )
    cached = CachedArtifacts(
        mass_properties=mass,
        step_url="https://example.com/step",
        glb_url="https://example.com/glb",
        svg_url="https://example.com/svg",
    )
    assert cached.step_url.startswith("https://")
