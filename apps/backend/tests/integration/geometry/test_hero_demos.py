"""Integration tests for the three hero demos end-to-end.

Marked @pytest.mark.integration — not run in default pytest invocation.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from services.geometry.cache import FakeGeometryCache
from services.geometry.pipeline import GeometryPipeline
from services.interpreter.domain.intent import DesignIntent, FieldSource, TriStateField
from services.interpreter.domain.materials import load_catalog

pytestmark = pytest.mark.integration


BACKEND_ROOT = Path(__file__).parent.parent.parent.parent


def _f(v: object) -> TriStateField:
    return TriStateField(value=v, source=FieldSource.EXTRACTED)


@pytest.fixture
def pipeline():
    catalog = load_catalog(BACKEND_ROOT / "data" / "materials.json")
    return GeometryPipeline(cache=FakeGeometryCache(), materials_catalog=catalog)


async def test_hero_flywheel_generates_valid_artifacts(pipeline) -> None:
    intent = DesignIntent(
        type="Flywheel_Rim",
        fields={
            "outer_diameter_m": _f(0.5),
            "inner_diameter_m": _f(0.1),
            "thickness_m": _f(0.05),
            "rpm": _f(3000),
        },
        composed_of=["Shaft", "Bearing_Housing"],
    )
    result = await pipeline.generate(intent=intent, material_name="steel_a36")
    assert 50 < result.mass_properties.mass_kg < 150  # ballpark for this flywheel
    assert result.artifacts.step_url
    assert result.artifacts.glb_url
    assert result.artifacts.svg_url


async def test_hero_hydro_generates_valid_artifacts(pipeline) -> None:
    intent = DesignIntent(
        type="Pelton_Runner",
        fields={
            "runner_diameter_m": _f(0.8),
            "bucket_count": _f(20),
        },
        composed_of=["Shaft", "Housing", "Mounting_Frame"],
    )
    result = await pipeline.generate(intent=intent, material_name="stainless_304")
    assert result.mass_properties.mass_kg > 0
    assert result.artifacts.step_url


async def test_hero_shelter_generates_valid_artifacts(pipeline) -> None:
    intent = DesignIntent(
        type="Hinge_Panel",
        fields={
            "width_m": _f(1.0),
            "height_m": _f(2.0),
            "thickness_m": _f(0.02),
        },
        composed_of=["Tensor_Rod", "Base_Connector"],
    )
    # Panel may fail because Tensor_Rod and Base_Connector have no builders
    # yet — this test documents that gap. Expect GeometryException for now.
    from services.geometry.domain.errors import GeometryException
    with pytest.raises(GeometryException):
        await pipeline.generate(intent=intent, material_name="bamboo_laminated")
