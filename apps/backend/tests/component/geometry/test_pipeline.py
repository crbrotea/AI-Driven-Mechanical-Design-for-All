"""Component tests for the Geometry pipeline orchestrator."""
from __future__ import annotations

from pathlib import Path

import pytest

from services.geometry.cache import FakeGeometryCache
from services.geometry.pipeline import GeometryPipeline
from services.interpreter.domain.intent import DesignIntent, FieldSource, TriStateField
from services.interpreter.domain.materials import load_catalog

BACKEND_ROOT = Path(__file__).parent.parent.parent.parent


@pytest.fixture
def catalog():
    return load_catalog(BACKEND_ROOT / "data" / "materials.json")


@pytest.fixture
def pipeline(catalog):
    return GeometryPipeline(
        cache=FakeGeometryCache(),
        materials_catalog=catalog,
    )


def _f(v: object) -> TriStateField:
    return TriStateField(value=v, source=FieldSource.EXTRACTED)


async def test_pipeline_builds_single_primitive_end_to_end(pipeline) -> None:
    intent = DesignIntent(
        type="Shaft",
        fields={"diameter_m": _f(0.05), "length_m": _f(0.5)},
    )
    result = await pipeline.generate(intent=intent, material_name="steel_a36")
    assert result.cache_hit is False
    assert result.intent_hash
    assert result.mass_properties.mass_kg > 0
    assert result.artifacts.step_url.startswith("fake://")


async def test_pipeline_second_call_hits_cache(pipeline) -> None:
    intent = DesignIntent(
        type="Shaft",
        fields={"diameter_m": _f(0.05), "length_m": _f(0.5)},
    )
    first = await pipeline.generate(intent=intent, material_name="steel_a36")
    second = await pipeline.generate(intent=intent, material_name="steel_a36")
    assert first.cache_hit is False
    assert second.cache_hit is True
    assert first.intent_hash == second.intent_hash


async def test_pipeline_raises_on_unknown_material(pipeline) -> None:
    from services.geometry.domain.errors import GeometryErrorCode, GeometryException
    intent = DesignIntent(
        type="Shaft",
        fields={"diameter_m": _f(0.05), "length_m": _f(0.5)},
    )
    with pytest.raises(GeometryException) as exc:
        await pipeline.generate(intent=intent, material_name="unobtanium")
    assert exc.value.error.code == GeometryErrorCode.MATERIAL_NOT_FOUND
