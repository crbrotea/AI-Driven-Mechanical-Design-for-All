"""Materials catalog loaded from a local JSON file."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

MaterialCategory = Literal["metal", "polymer", "composite", "ceramic"]


class MaterialProperties(BaseModel):
    """Full properties of a single material (SI units throughout)."""

    model_config = ConfigDict(frozen=True)

    name: str
    display_name: str
    category: MaterialCategory
    density_kg_m3: float
    young_modulus_gpa: float
    yield_strength_mpa: float
    ultimate_tensile_strength_mpa: float
    thermal_conductivity_w_m_k: float
    max_service_temperature_c: float
    relative_cost_index: float
    sustainability_score: float  # 0..1


class MaterialRef(BaseModel):
    """Lightweight reference returned by search_materials()."""

    model_config = ConfigDict(frozen=True)

    name: str
    display_name: str
    category: MaterialCategory
    density_kg_m3: float
    sustainability_score: float


class MaterialsCatalog:
    """In-memory catalog of materials, loaded at service startup."""

    def __init__(self, materials: list[MaterialProperties]) -> None:
        self._by_name = {m.name: m for m in materials}

    def names(self) -> set[str]:
        return set(self._by_name.keys())

    def get(self, name: str) -> MaterialProperties:
        if name not in self._by_name:
            raise KeyError(f"Unknown material: {name}")
        return self._by_name[name]

    def search(
        self,
        *,
        category: MaterialCategory | None = None,
        max_density_kg_m3: float | None = None,
        min_yield_strength_mpa: float | None = None,
        min_sustainability: float | None = None,
    ) -> list[MaterialRef]:
        results: list[MaterialRef] = []
        for m in self._by_name.values():
            if category is not None and m.category != category:
                continue
            if max_density_kg_m3 is not None and m.density_kg_m3 > max_density_kg_m3:
                continue
            if (
                min_yield_strength_mpa is not None
                and m.yield_strength_mpa < min_yield_strength_mpa
            ):
                continue
            if (
                min_sustainability is not None
                and m.sustainability_score < min_sustainability
            ):
                continue
            results.append(
                MaterialRef(
                    name=m.name,
                    display_name=m.display_name,
                    category=m.category,
                    density_kg_m3=m.density_kg_m3,
                    sustainability_score=m.sustainability_score,
                )
            )
        return results


def load_catalog(path: Path) -> MaterialsCatalog:
    """Load a MaterialsCatalog from a JSON file at `path`."""
    data = json.loads(path.read_text(encoding="utf-8"))
    materials = [MaterialProperties.model_validate(m) for m in data["materials"]]
    return MaterialsCatalog(materials)
