"""Physical range and cross-field consistency validators for DesignIntent."""
from __future__ import annotations

from services.interpreter.domain.errors import (
    ErrorCode,
    InterpreterError,
)
from services.interpreter.domain.intent import DesignIntent, FieldSource
from services.interpreter.domain.primitives_registry import (
    PrimitiveSchema,
    PrimitivesRegistry,
)

# Cross-field consistency rules per primitive type.
_CROSS_FIELD_RULES: dict[str, list[tuple[str, str, str]]] = {
    # (field_a, field_b, relation) — enforces field_a < field_b.
    "Flywheel_Rim": [("inner_diameter_m", "outer_diameter_m", "<")],
}


def validate_physical_consistency(
    intent: DesignIntent, registry: PrimitivesRegistry
) -> None:
    """Validate `intent` against `registry`. Raises InterpreterException on failure."""
    try:
        schema = registry.get(intent.type)
    except KeyError:
        InterpreterError(
            code=ErrorCode.UNKNOWN_PRIMITIVE,
            message=f"Primitive '{intent.type}' is not registered.",
            field=None,
            details={"type": intent.type},
        ).raise_as()

    _validate_required_fields_present(intent, schema)
    _validate_field_ranges(intent, schema)
    _validate_cross_field_consistency(intent)


def _validate_required_fields_present(
    intent: DesignIntent, schema: PrimitiveSchema
) -> None:
    for name, spec in schema.params.items():
        if not spec.required:
            continue
        if name not in intent.fields:
            InterpreterError(
                code=ErrorCode.PHYSICAL_RANGE_VIOLATION,
                message=f"Required field '{name}' is absent.",
                field=name,
            ).raise_as()


def _validate_field_ranges(intent: DesignIntent, schema: PrimitiveSchema) -> None:
    for name, field in intent.fields.items():
        if name not in schema.params:
            continue  # Unknown params from LLM are tolerated, not validated.
        if field.source == FieldSource.MISSING:
            continue
        spec = schema.params[name]
        if spec.type in ("float", "int"):
            raw = field.value
            if not isinstance(raw, (int, float)):
                InterpreterError(
                    code=ErrorCode.PHYSICAL_RANGE_VIOLATION,
                    message=f"Field '{name}' must be numeric.",
                    field=name,
                ).raise_as()
                continue  # unreachable; guides mypy past the isinstance guard
            value: int | float = raw
            if spec.min is not None and value < spec.min:
                InterpreterError(
                    code=ErrorCode.PHYSICAL_RANGE_VIOLATION,
                    message=(
                        f"Field '{name}' value {value} is below minimum {spec.min}."
                    ),
                    field=name,
                ).raise_as()
            if spec.max is not None and value > spec.max:
                InterpreterError(
                    code=ErrorCode.PHYSICAL_RANGE_VIOLATION,
                    message=(
                        f"Field '{name}' value {value} exceeds maximum {spec.max}."
                    ),
                    field=name,
                ).raise_as()


def _validate_cross_field_consistency(intent: DesignIntent) -> None:
    rules = _CROSS_FIELD_RULES.get(intent.type, [])
    for a, b, relation in rules:
        fa = intent.fields.get(a)
        fb = intent.fields.get(b)
        if fa is None or fb is None:
            continue
        if fa.source == FieldSource.MISSING or fb.source == FieldSource.MISSING:
            continue
        assert fa.value is not None and fb.value is not None  # guarded by MISSING check above
        va: float = float(fa.value)
        vb: float = float(fb.value)
        if relation == "<" and not (va < vb):
            InterpreterError(
                code=ErrorCode.PHYSICAL_RANGE_VIOLATION,
                message=f"'{a}' must be less than '{b}' (got {va} vs {vb}).",
                field=a,
            ).raise_as()
