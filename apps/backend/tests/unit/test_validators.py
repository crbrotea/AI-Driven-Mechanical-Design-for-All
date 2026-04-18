"""Unit tests for physical range validators."""
from __future__ import annotations

import pytest

from services.interpreter.domain.errors import ErrorCode, InterpreterException
from services.interpreter.domain.intent import (
    DesignIntent,
    FieldSource,
    TriStateField,
)
from services.interpreter.domain.primitives_registry import DEFAULT_REGISTRY
from services.interpreter.domain.validators import validate_physical_consistency


def _field(value: float | int | str, source: FieldSource = FieldSource.EXTRACTED) -> TriStateField:
    return TriStateField(value=value, source=source)


def test_valid_flywheel_passes() -> None:
    intent = DesignIntent(
        type="Flywheel_Rim",
        fields={
            "outer_diameter_m": _field(0.5),
            "inner_diameter_m": _field(0.1),
            "thickness_m": _field(0.05),
            "rpm": _field(3000),
        },
    )
    validate_physical_consistency(intent, DEFAULT_REGISTRY)  # no raise


def test_inner_diameter_not_smaller_than_outer_raises() -> None:
    intent = DesignIntent(
        type="Flywheel_Rim",
        fields={
            "outer_diameter_m": _field(0.5),
            "inner_diameter_m": _field(0.6),
            "thickness_m": _field(0.05),
            "rpm": _field(3000),
        },
    )
    with pytest.raises(InterpreterException) as exc:
        validate_physical_consistency(intent, DEFAULT_REGISTRY)
    assert exc.value.error.code == ErrorCode.PHYSICAL_RANGE_VIOLATION
    assert exc.value.error.field == "inner_diameter_m"


def test_value_below_range_raises() -> None:
    intent = DesignIntent(
        type="Shaft",
        fields={
            "diameter_m": _field(0.0005),  # min is 0.001
            "length_m": _field(0.5),
        },
    )
    with pytest.raises(InterpreterException) as exc:
        validate_physical_consistency(intent, DEFAULT_REGISTRY)
    assert exc.value.error.code == ErrorCode.PHYSICAL_RANGE_VIOLATION
    assert exc.value.error.field == "diameter_m"


def test_value_above_range_raises() -> None:
    intent = DesignIntent(
        type="Flywheel_Rim",
        fields={
            "outer_diameter_m": _field(0.5),
            "inner_diameter_m": _field(0.1),
            "thickness_m": _field(0.05),
            "rpm": _field(100000),  # max is 60000
        },
    )
    with pytest.raises(InterpreterException) as exc:
        validate_physical_consistency(intent, DEFAULT_REGISTRY)
    assert exc.value.error.field == "rpm"


def test_unknown_primitive_raises_unknown_primitive_error() -> None:
    intent = DesignIntent(
        type="SuperFlywheel",
        fields={"outer_diameter_m": _field(0.5)},
    )
    with pytest.raises(InterpreterException) as exc:
        validate_physical_consistency(intent, DEFAULT_REGISTRY)
    assert exc.value.error.code == ErrorCode.UNKNOWN_PRIMITIVE


def test_missing_fields_are_not_validated_for_range() -> None:
    # Missing fields are expected during extraction; they skip range check.
    intent = DesignIntent(
        type="Flywheel_Rim",
        fields={
            "outer_diameter_m": _field(0.5),
            "inner_diameter_m": TriStateField(
                value=None, source=FieldSource.MISSING, required=True
            ),
            "thickness_m": _field(0.05),
            "rpm": _field(3000),
        },
    )
    validate_physical_consistency(intent, DEFAULT_REGISTRY)  # no raise


def test_required_field_absent_raises() -> None:
    # thickness_m is required but absent from fields dict entirely.
    intent = DesignIntent(
        type="Flywheel_Rim",
        fields={
            "outer_diameter_m": _field(0.5),
            "inner_diameter_m": _field(0.1),
            "rpm": _field(3000),
        },
    )
    with pytest.raises(InterpreterException) as exc:
        validate_physical_consistency(intent, DEFAULT_REGISTRY)
    assert exc.value.error.code == ErrorCode.PHYSICAL_RANGE_VIOLATION
    assert exc.value.error.field == "thickness_m"


def test_unknown_param_name_is_ignored() -> None:
    # Extra fields from LLM hallucination should NOT fail validation;
    # they are simply ignored in range checks.
    intent = DesignIntent(
        type="Flywheel_Rim",
        fields={
            "outer_diameter_m": _field(0.5),
            "inner_diameter_m": _field(0.1),
            "thickness_m": _field(0.05),
            "rpm": _field(3000),
            "magical_field": _field("unknown"),
        },
    )
    validate_physical_consistency(intent, DEFAULT_REGISTRY)  # no raise
