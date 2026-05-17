"""Composer — orchestrates primitive builders and composition rules."""
from __future__ import annotations

import inspect
from collections.abc import Callable
from typing import Any

from build123d import Compound, Part, ShapeList

from services.geometry.builders import get_builder
from services.geometry.composition_rules import COMPOSITION_RULES
from services.geometry.domain.errors import GeometryError, GeometryErrorCode
from services.interpreter.domain.intent import DesignIntent, FieldSource


def _builder_args(builder: Callable[..., Any], fields: dict[str, Any]) -> dict[str, Any]:
    """Filter `fields` down to the kwargs the builder actually accepts.

    Intent fields can carry analysis-only data (e.g. head_m, flow_m3_s on a
    Pelton runner) that the geometry builder does not consume. Splatting the
    full dict would raise TypeError on the unknown kwargs.
    """
    accepted = set(inspect.signature(builder).parameters)
    return {k: v for k, v in fields.items() if k in accepted}


def compose_assembly(intent: DesignIntent) -> Compound:
    """Build main primitive + composed primitives, then fuse them."""
    main_fields = _extract_numeric_values(intent.fields)
    main_builder = get_builder(intent.type)
    try:
        main_part: Part = main_builder(**_builder_args(main_builder, main_fields))
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
            # The interpreter occasionally proposes companion parts that
            # have no composition rule (e.g. Hinge_Panel paired with
            # Mounting_Frame, copied from the Pelton few-shot). Skip them
            # rather than failing the whole assembly.
            continue
        composed_fields = rule(main_fields)  # type: ignore[misc]
        composed_builder = get_builder(composed_name)
        try:
            composed_part: Part = composed_builder(
                **_builder_args(composed_builder, composed_fields)
            )
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
    children = list(result) if isinstance(result, ShapeList) else [result]
    return Compound(children=children)


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
