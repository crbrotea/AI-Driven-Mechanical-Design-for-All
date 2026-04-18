"""Unit tests for the primitives registry."""
from __future__ import annotations

import pytest

from services.interpreter.domain.primitives_registry import (
    DEFAULT_REGISTRY,
    PARAM_TYPE_FLOAT,
    ParamSpec,
    PrimitiveSchema,
    PrimitivesRegistry,
)


@pytest.fixture
def registry() -> PrimitivesRegistry:
    return PrimitivesRegistry(
        [
            PrimitiveSchema(
                name="Flywheel_Rim",
                category="rotational",
                description="Rim with mass concentrated at periphery.",
                params={
                    "outer_diameter_m": ParamSpec(
                        type=PARAM_TYPE_FLOAT, min=0.05, max=3.0, required=True
                    ),
                    "inner_diameter_m": ParamSpec(
                        type=PARAM_TYPE_FLOAT, min=0.0, max=2.8, required=True
                    ),
                    "thickness_m": ParamSpec(
                        type=PARAM_TYPE_FLOAT, min=0.005, max=0.5, required=True
                    ),
                },
                composable_with=["Shaft"],
            ),
            PrimitiveSchema(
                name="Shaft",
                category="rotational",
                description="Cylindrical rotating element.",
                params={
                    "diameter_m": ParamSpec(
                        type=PARAM_TYPE_FLOAT, min=0.001, max=1.0, required=True
                    ),
                    "length_m": ParamSpec(
                        type=PARAM_TYPE_FLOAT, min=0.01, max=10.0, required=True
                    ),
                },
            ),
        ]
    )


def test_list_returns_all_summaries(registry: PrimitivesRegistry) -> None:
    summaries = registry.list_summaries()
    assert len(summaries) == 2
    assert summaries[0].name == "Flywheel_Rim"
    assert summaries[1].category == "rotational"


def test_get_by_name_returns_full_schema(registry: PrimitivesRegistry) -> None:
    schema = registry.get("Flywheel_Rim")
    assert schema.name == "Flywheel_Rim"
    assert "outer_diameter_m" in schema.params
    assert schema.params["outer_diameter_m"].min == 0.05


def test_get_unknown_raises_keyerror(registry: PrimitivesRegistry) -> None:
    with pytest.raises(KeyError, match="Unknown primitive: SuperFlywheel"):
        registry.get("SuperFlywheel")


def test_case_sensitive_lookup(registry: PrimitivesRegistry) -> None:
    with pytest.raises(KeyError):
        registry.get("flywheel_rim")


def test_default_registry_contains_hero_demo_primitives() -> None:
    names = DEFAULT_REGISTRY.names()
    # Hero 1 — Flywheel
    assert "Flywheel_Rim" in names
    assert "Shaft" in names
    assert "Bearing_Housing" in names
    # Hero 2 — Hydroelectric
    assert "Pelton_Runner" in names
    assert "Housing" in names
    assert "Mounting_Frame" in names
    # Hero 3 — Shelter
    assert "Hinge_Panel" in names
