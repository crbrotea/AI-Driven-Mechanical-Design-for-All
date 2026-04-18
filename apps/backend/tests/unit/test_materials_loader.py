"""Unit tests for the materials catalog loader."""
from __future__ import annotations

from pathlib import Path

import pytest

from services.interpreter.domain.materials import (
    MaterialProperties,
    MaterialsCatalog,
    load_catalog,
)


@pytest.fixture
def catalog() -> MaterialsCatalog:
    root = Path(__file__).parent.parent.parent / "data"
    return load_catalog(root / "materials.json")


def test_catalog_has_seed_materials(catalog: MaterialsCatalog) -> None:
    names = catalog.names()
    assert "steel_a36" in names
    assert "aluminum_6061" in names
    assert "pla_biodegradable" in names
    assert "bamboo_laminated" in names
    assert len(names) >= 7


def test_get_material_returns_properties(catalog: MaterialsCatalog) -> None:
    mat = catalog.get("steel_a36")
    assert isinstance(mat, MaterialProperties)
    assert mat.density_kg_m3 == 7850
    assert mat.yield_strength_mpa == 250


def test_get_unknown_raises_keyerror(catalog: MaterialsCatalog) -> None:
    with pytest.raises(KeyError, match="Unknown material: unobtanium"):
        catalog.get("unobtanium")


def test_search_by_category(catalog: MaterialsCatalog) -> None:
    metals = catalog.search(category="metal")
    names = {m.name for m in metals}
    assert "steel_a36" in names
    assert "aluminum_6061" in names
    assert "pla_biodegradable" not in names


def test_search_by_sustainability(catalog: MaterialsCatalog) -> None:
    sustainable = catalog.search(min_sustainability=0.9)
    names = {m.name for m in sustainable}
    assert "pla_biodegradable" in names
    assert "bamboo_laminated" in names
    assert "steel_a36" not in names


def test_search_by_max_density(catalog: MaterialsCatalog) -> None:
    light = catalog.search(max_density_kg_m3=2000)
    for m in light:
        assert m.density_kg_m3 <= 2000
