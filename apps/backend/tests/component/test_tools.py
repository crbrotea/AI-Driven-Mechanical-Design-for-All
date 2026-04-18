"""Component tests for the 4 Gemma 4 tools."""
from __future__ import annotations

from pathlib import Path

import pytest

from services.interpreter.domain.materials import MaterialsCatalog, load_catalog
from services.interpreter.domain.primitives_registry import DEFAULT_REGISTRY
from services.interpreter.tools.materials import (
    build_materials_tools,
    get_material_properties,
    search_materials,
)
from services.interpreter.tools.primitives import (
    build_primitives_tools,
    get_primitive_schema,
    list_primitives,
)
from services.interpreter.tools.registry import ToolRegistry


@pytest.fixture
def catalog() -> MaterialsCatalog:
    root = Path(__file__).parent.parent.parent / "data"
    return load_catalog(root / "materials.json")


def test_list_primitives_returns_all_registered() -> None:
    result = list_primitives(DEFAULT_REGISTRY)
    names = [s["name"] for s in result]
    assert "Flywheel_Rim" in names
    assert "Pelton_Runner" in names


def test_get_primitive_schema_returns_full_params() -> None:
    result = get_primitive_schema(DEFAULT_REGISTRY, name="Flywheel_Rim")
    assert result["name"] == "Flywheel_Rim"
    assert "outer_diameter_m" in result["params"]
    assert result["params"]["outer_diameter_m"]["min"] == 0.05


def test_get_primitive_schema_unknown_raises() -> None:
    with pytest.raises(KeyError):
        get_primitive_schema(DEFAULT_REGISTRY, name="SuperFlywheel")


def test_search_materials_filters_correctly(catalog: MaterialsCatalog) -> None:
    result = search_materials(catalog, criteria={"category": "metal"})
    assert len(result) >= 3
    for m in result:
        assert m["category"] == "metal"


def test_get_material_properties_returns_full(catalog: MaterialsCatalog) -> None:
    result = get_material_properties(catalog, name="aluminum_6061")
    assert result["density_kg_m3"] == 2700
    assert result["yield_strength_mpa"] == 276


def test_registry_dispatches_by_name(catalog: MaterialsCatalog) -> None:
    registry = ToolRegistry(
        tools={
            **build_primitives_tools(DEFAULT_REGISTRY),
            **build_materials_tools(catalog),
        }
    )
    assert set(registry.names()) == {
        "list_primitives",
        "get_primitive_schema",
        "search_materials",
        "get_material_properties",
    }
    result = registry.invoke("get_primitive_schema", {"name": "Shaft"})
    assert result["name"] == "Shaft"


def test_registry_unknown_tool_raises(catalog: MaterialsCatalog) -> None:
    registry = ToolRegistry(tools=build_primitives_tools(DEFAULT_REGISTRY))
    with pytest.raises(KeyError, match="Unknown tool: make_coffee"):
        registry.invoke("make_coffee", {})
