"""Primitives registry — source of truth for what Gemma 4 can compose."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

PARAM_TYPE_FLOAT: Literal["float"] = "float"
PARAM_TYPE_INT: Literal["int"] = "int"
PARAM_TYPE_STRING: Literal["string"] = "string"
ParamType = Literal["float", "int", "string"]


class ParamSpec(BaseModel):
    """Specification of a single primitive parameter."""

    model_config = ConfigDict(frozen=True)

    type: ParamType
    min: float | None = None
    max: float | None = None
    required: bool = True
    description: str | None = None
    allowed_values: list[str] | None = None


class PrimitiveSchema(BaseModel):
    """Full schema of a single primitive exposed to Gemma 4."""

    model_config = ConfigDict(frozen=True)

    name: str
    category: str  # e.g. "rotational", "structural", "articulated"
    description: str
    params: dict[str, ParamSpec]
    composable_with: list[str] = []


class PrimitiveSummary(BaseModel):
    """Lightweight summary returned by list_primitives()."""

    model_config = ConfigDict(frozen=True)

    name: str
    category: str
    description: str


class PrimitivesRegistry:
    """In-memory registry of primitives. Populated from Python code."""

    def __init__(self, schemas: list[PrimitiveSchema]) -> None:
        self._schemas = {s.name: s for s in schemas}

    def list_summaries(self) -> list[PrimitiveSummary]:
        return [
            PrimitiveSummary(
                name=s.name, category=s.category, description=s.description
            )
            for s in self._schemas.values()
        ]

    def get(self, name: str) -> PrimitiveSchema:
        if name not in self._schemas:
            raise KeyError(f"Unknown primitive: {name}")
        return self._schemas[name]

    def names(self) -> set[str]:
        return set(self._schemas.keys())


def _build_default_registry() -> PrimitivesRegistry:
    """Initial primitives covering the 3 hero demos."""
    return PrimitivesRegistry([
        PrimitiveSchema(
            name="Flywheel_Rim",
            category="rotational",
            description="Rim with mass concentrated at the periphery for energy storage.",
            params={
                "outer_diameter_m": ParamSpec(
                    type=PARAM_TYPE_FLOAT, min=0.05, max=3.0, required=True,
                    description="Outer rim diameter in meters.",
                ),
                "inner_diameter_m": ParamSpec(
                    type=PARAM_TYPE_FLOAT, min=0.0, max=2.8, required=True,
                    description="Inner hole diameter in meters.",
                ),
                "thickness_m": ParamSpec(
                    type=PARAM_TYPE_FLOAT, min=0.005, max=0.5, required=True,
                    description="Axial thickness of the rim in meters.",
                ),
                "rpm": ParamSpec(
                    type=PARAM_TYPE_FLOAT, min=10, max=60000, required=True,
                    description="Rotational speed in revolutions per minute.",
                ),
            },
            composable_with=["Shaft", "Bearing_Housing"],
        ),
        PrimitiveSchema(
            name="Shaft",
            category="rotational",
            description="Cylindrical rotating element transmitting torque.",
            params={
                "diameter_m": ParamSpec(
                    type=PARAM_TYPE_FLOAT, min=0.001, max=1.0, required=True,
                ),
                "length_m": ParamSpec(
                    type=PARAM_TYPE_FLOAT, min=0.01, max=10.0, required=True,
                ),
            },
            composable_with=["Flywheel_Rim", "Pelton_Runner", "Bearing_Housing"],
        ),
        PrimitiveSchema(
            name="Bearing_Housing",
            category="structural",
            description="Support housing for a shaft bearing.",
            params={
                "bore_diameter_m": ParamSpec(
                    type=PARAM_TYPE_FLOAT, min=0.001, max=1.0, required=True,
                ),
                "outer_diameter_m": ParamSpec(
                    type=PARAM_TYPE_FLOAT, min=0.01, max=2.0, required=True,
                ),
            },
            composable_with=["Shaft"],
        ),
        PrimitiveSchema(
            name="Pelton_Runner",
            category="rotational",
            description="Simplified Pelton hydro-turbine runner.",
            params={
                "runner_diameter_m": ParamSpec(
                    type=PARAM_TYPE_FLOAT, min=0.1, max=5.0, required=True,
                ),
                "bucket_count": ParamSpec(
                    type=PARAM_TYPE_INT, min=12, max=30, required=True,
                ),
            },
            composable_with=["Shaft", "Housing", "Mounting_Frame"],
        ),
        PrimitiveSchema(
            name="Housing",
            category="structural",
            description="Enclosure around rotating machinery.",
            params={
                "inner_diameter_m": ParamSpec(
                    type=PARAM_TYPE_FLOAT, min=0.1, max=5.0, required=True,
                ),
                "wall_thickness_m": ParamSpec(
                    type=PARAM_TYPE_FLOAT, min=0.002, max=0.1, required=True,
                ),
            },
            composable_with=["Pelton_Runner", "Mounting_Frame"],
        ),
        PrimitiveSchema(
            name="Mounting_Frame",
            category="structural",
            description="Modular base frame for mounting machinery.",
            params={
                "length_m": ParamSpec(
                    type=PARAM_TYPE_FLOAT, min=0.2, max=5.0, required=True,
                ),
                "width_m": ParamSpec(
                    type=PARAM_TYPE_FLOAT, min=0.2, max=3.0, required=True,
                ),
                "height_m": ParamSpec(
                    type=PARAM_TYPE_FLOAT, min=0.05, max=1.0, required=True,
                ),
            },
        ),
        PrimitiveSchema(
            name="Hinge_Panel",
            category="articulated",
            description="Rigid panel hinged at one edge, used in foldable structures.",
            params={
                "width_m": ParamSpec(
                    type=PARAM_TYPE_FLOAT, min=0.1, max=4.0, required=True,
                ),
                "height_m": ParamSpec(
                    type=PARAM_TYPE_FLOAT, min=0.1, max=3.0, required=True,
                ),
                "thickness_m": ParamSpec(
                    type=PARAM_TYPE_FLOAT, min=0.005, max=0.05, required=True,
                ),
            },
            composable_with=["Tensor_Rod", "Base_Connector"],
        ),
    ])


DEFAULT_REGISTRY = _build_default_registry()
