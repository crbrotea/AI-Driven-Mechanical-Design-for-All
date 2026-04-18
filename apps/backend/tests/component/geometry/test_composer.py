"""Component tests for the Composer."""
from __future__ import annotations

import pytest

from services.geometry.composer import compose_assembly
from services.geometry.domain.errors import GeometryErrorCode, GeometryException
from services.interpreter.domain.intent import (
    DesignIntent,
    FieldSource,
    TriStateField,
)


def _f(v: object) -> TriStateField:
    return TriStateField(value=v, source=FieldSource.EXTRACTED)


def test_single_primitive_produces_compound() -> None:
    intent = DesignIntent(
        type="Shaft",
        fields={"diameter_m": _f(0.05), "length_m": _f(0.5)},
    )
    compound = compose_assembly(intent)
    assert compound.volume > 0


def test_composed_intent_fuses_parts() -> None:
    intent = DesignIntent(
        type="Flywheel_Rim",
        fields={
            "outer_diameter_m": _f(0.5),
            "inner_diameter_m": _f(0.1),
            "thickness_m": _f(0.05),
            "rpm": _f(3000),
        },
        composed_of=["Shaft"],
    )
    compound = compose_assembly(intent)
    # Fused volume must be >= main primitive's volume
    from services.geometry.primitives.flywheel_rim import build_flywheel_rim
    main = build_flywheel_rim(0.5, 0.1, 0.05)
    assert compound.volume >= main.volume * 0.95  # allow minor boolean artifacts


def test_missing_composition_rule_raises() -> None:
    intent = DesignIntent(
        type="Flywheel_Rim",
        fields={
            "outer_diameter_m": _f(0.5),
            "inner_diameter_m": _f(0.1),
            "thickness_m": _f(0.05),
            "rpm": _f(3000),
        },
        composed_of=["Pelton_Runner"],  # no rule for this pair
    )
    with pytest.raises(GeometryException) as exc:
        compose_assembly(intent)
    assert exc.value.error.code == GeometryErrorCode.COMPOSITION_RULE_MISSING


def test_unknown_primitive_raises() -> None:
    intent = DesignIntent(
        type="NotARealPrimitive",
        fields={"x": _f(1.0)},
    )
    with pytest.raises(GeometryException) as exc:
        compose_assembly(intent)
    assert exc.value.error.code == GeometryErrorCode.UNKNOWN_PRIMITIVE
