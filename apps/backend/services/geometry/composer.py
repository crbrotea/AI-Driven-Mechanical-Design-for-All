"""Composer — orchestrates primitive builders and composition rules."""
from __future__ import annotations

from typing import Any

from build123d import Compound, Part

from services.geometry.builders import get_builder
from services.geometry.composition_rules import COMPOSITION_RULES
from services.geometry.domain.errors import GeometryError, GeometryErrorCode
from services.interpreter.domain.intent import DesignIntent, FieldSource


def compose_assembly(intent: DesignIntent) -> Compound:
    """Build main primitive + composed primitives, then fuse them."""
    main_fields = _extract_numeric_values(intent.fields)
    main_builder = get_builder(intent.type)
    try:
        main_part: Part = main_builder(**main_fields)
    except (ValueError, TypeError) as e:
        GeometryError(
            code=GeometryErrorCode.PARAMETER_OUT_OF_RANGE,
            message=str(e),
            primitive=intent.type,
            stage="build",
        ).raise_as()
        raise  # unreachable, for mypy

    parts: list[Part] = [main_part]
    for composed_name in intent.composed_of:
        key = (intent.type, composed_name)
        rule = COMPOSITION_RULES.get(key)
        if rule is None:
            GeometryError(
                code=GeometryErrorCode.COMPOSITION_RULE_MISSING,
                message=f"No composition rule for {key}",
                primitive=composed_name,
                stage="build",
                details={"main": intent.type, "composed": composed_name},
            ).raise_as()
        composed_fields = rule(main_fields)  # type: ignore[misc]
        composed_builder = get_builder(composed_name)
        try:
            composed_part: Part = composed_builder(**composed_fields)
        except (ValueError, TypeError) as e:
            GeometryError(
                code=GeometryErrorCode.PARAMETER_OUT_OF_RANGE,
                message=str(e),
                primitive=composed_name,
                stage="build",
            ).raise_as()
            raise
        parts.append(composed_part)

    return _fuse(parts)


def _fuse(parts: list[Part]) -> Compound:
    """Boolean union of all parts into a single Compound."""
    if len(parts) == 1:
        return Compound(children=[parts[0]])
    try:
        result: Part = parts[0]
        for p in parts[1:]:
            result = result + p
    except Exception as e:
        GeometryError(
            code=GeometryErrorCode.BOOLEAN_OPERATION_FAILED,
            message=f"Boolean union failed: {e}",
            stage="build",
        ).raise_as()
        raise
    return Compound(children=[result])


def _extract_numeric_values(
    fields: dict[str, Any],
) -> dict[str, Any]:
    """Extract raw .value from TriStateField map, skipping missing fields."""
    result: dict[str, Any] = {}
    for name, field in fields.items():
        if field.source == FieldSource.MISSING:
            continue
        result[name] = field.value
    return result
