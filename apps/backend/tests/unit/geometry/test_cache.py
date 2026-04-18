"""Unit tests for GeometryCache and intent hasher."""
from __future__ import annotations

from services.geometry.cache import (
    FakeGeometryCache,
    compute_intent_hash,
)
from services.geometry.domain.artifacts import (
    BuiltArtifacts,
    MassProperties,
)
from services.interpreter.domain.intent import (
    DesignIntent,
    FieldSource,
    TriStateField,
)


def _intent(type_: str, **fields: float) -> DesignIntent:
    return DesignIntent(
        type=type_,
        fields={
            name: TriStateField(value=v, source=FieldSource.EXTRACTED)
            for name, v in fields.items()
        },
    )


def test_hash_ignores_tri_state_metadata() -> None:
    i1 = DesignIntent(type="Shaft", fields={
        "diameter_m": TriStateField(value=0.05, source=FieldSource.EXTRACTED),
    })
    i2 = DesignIntent(type="Shaft", fields={
        "diameter_m": TriStateField(value=0.05, source=FieldSource.DEFAULTED, reason="x"),
    })
    assert compute_intent_hash(i1) == compute_intent_hash(i2)


def test_hash_changes_on_value_change() -> None:
    assert compute_intent_hash(_intent("Shaft", diameter_m=0.05, length_m=0.5)) != \
           compute_intent_hash(_intent("Shaft", diameter_m=0.06, length_m=0.5))


def test_hash_is_16_chars() -> None:
    h = compute_intent_hash(_intent("Shaft", diameter_m=0.05, length_m=0.5))
    assert len(h) == 16


def test_hash_ignores_composed_order() -> None:
    i1 = DesignIntent(
        type="Flywheel_Rim",
        fields={"outer_diameter_m": TriStateField(value=0.5, source=FieldSource.EXTRACTED)},
        composed_of=["Shaft", "Bearing_Housing"],
    )
    i2 = DesignIntent(
        type="Flywheel_Rim",
        fields={"outer_diameter_m": TriStateField(value=0.5, source=FieldSource.EXTRACTED)},
        composed_of=["Bearing_Housing", "Shaft"],
    )
    assert compute_intent_hash(i1) == compute_intent_hash(i2)


async def test_fake_cache_miss_returns_none() -> None:
    cache = FakeGeometryCache()
    result = await cache.lookup("nonexistent")
    assert result is None


async def test_fake_cache_store_then_lookup_roundtrip() -> None:
    cache = FakeGeometryCache()
    mass = MassProperties(
        volume_m3=0.01, mass_kg=78.5,
        center_of_mass=(0, 0, 0.025),
        bbox_m=(0, 0, 0, 0.5, 0.5, 0.05),
    )
    artifacts = BuiltArtifacts(
        step_bytes=b"ISO-10303-21;",
        glb_bytes=b"glTF",
        svg_bytes=b"<svg></svg>",
        mass=mass,
    )
    await cache.store("abc123", artifacts)
    result = await cache.lookup("abc123")
    assert result is not None
    assert result.mass_properties.mass_kg == 78.5
