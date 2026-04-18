"""Gemma 4 tools for material search and property lookup."""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from services.interpreter.domain.materials import MaterialsCatalog


def search_materials(
    catalog: MaterialsCatalog, *, criteria: dict[str, Any]
) -> list[dict[str, Any]]:
    """Tool: filter the materials catalog by criteria."""
    refs = catalog.search(
        category=criteria.get("category"),
        max_density_kg_m3=criteria.get("max_density_kg_m3"),
        min_yield_strength_mpa=criteria.get("min_yield_strength_mpa"),
        min_sustainability=criteria.get("min_sustainability"),
    )
    return [r.model_dump() for r in refs]


def get_material_properties(
    catalog: MaterialsCatalog, *, name: str
) -> dict[str, Any]:
    """Tool: return full properties of material `name`."""
    return catalog.get(name).model_dump()


def build_materials_tools(
    catalog: MaterialsCatalog,
) -> dict[str, Callable[..., Any]]:
    """Return tool callables bound to the given catalog."""
    return {
        "search_materials": lambda args: search_materials(
            catalog, criteria=args.get("criteria", {})
        ),
        "get_material_properties": lambda args: get_material_properties(
            catalog, name=args["name"]
        ),
    }
