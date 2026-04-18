"""Parse arbitrary unit expressions and normalize to SI.

Uses `pint` as the underlying unit library. Dimensionless quantities
(pure numbers) return an empty unit_si string. RPM is treated as a
canonical engineering unit and kept as-is (not converted to rad/s).
"""
from __future__ import annotations

from dataclasses import dataclass

import pint

from services.interpreter.domain.errors import (
    ErrorCode,
    InterpreterError,
)

_UREG: pint.UnitRegistry[pint.util.UnitsContainer] = pint.UnitRegistry()

# Mapping of canonical SI base units used as the output unit_si string.
# Simple (single-unit) lookup by first token.
_SI_OUTPUT_MAP: dict[str, str] = {
    "meter": "m",
    "kilogram": "kg",
    "second": "s",
    "kelvin": "K",
    "pascal": "Pa",
    "newton": "N",
    "joule": "J",
    "watt": "W",
}

# Full base-unit-string → friendly SI symbol for compound derived units.
# Pint expresses these as "kilogram / meter / second ** 2" etc.
_SI_COMPOUND_MAP: dict[str, str] = {
    "kilogram / meter / second ** 2": "Pa",
    "kilogram * meter / second ** 2": "N",
    "kilogram * meter ** 2 / second ** 2": "J",
    "kilogram * meter ** 2 / second ** 3": "W",
}

# Units we keep as-is (no conversion), by canonical pint name.
_NON_SI_KEPT_AS_IS: set[str] = {"revolutions_per_minute"}


@dataclass(frozen=True)
class NormalizedValue:
    """A scalar value in SI with its original expression preserved."""

    value: float
    unit_si: str
    original: str


def normalize(expression: str) -> NormalizedValue:
    """Parse `expression` and convert to SI. Raises InterpreterException on failure."""
    try:
        quantity = _UREG.Quantity(expression)
    except (
        pint.errors.UndefinedUnitError,
        pint.errors.DimensionalityError,
        ValueError,
    ) as e:
        InterpreterError(
            code=ErrorCode.UNIT_PARSE_FAILED,
            message=f"Could not parse '{expression}' as a valid unit expression.",
            details={"error": str(e)},
        ).raise_as()

    # Dimensionless (pure number)
    if quantity.dimensionless:
        return NormalizedValue(
            value=float(quantity.magnitude), unit_si="", original=expression
        )

    # Keep RPM-like units as-is
    canonical = str(quantity.units)
    if canonical in _NON_SI_KEPT_AS_IS:
        return NormalizedValue(
            value=float(quantity.magnitude),
            unit_si="rpm",
            original=expression,
        )

    # Convert to SI base units
    try:
        si_quantity = quantity.to_base_units()
    except pint.errors.DimensionalityError as e:
        InterpreterError(
            code=ErrorCode.UNIT_PARSE_FAILED,
            message=f"Cannot convert '{expression}' to SI base units.",
            details={"error": str(e)},
        ).raise_as()

    base_unit_str = str(si_quantity.units)
    # Try compound map first, then single-token map, then raw pint string.
    if base_unit_str in _SI_COMPOUND_MAP:
        unit_si = _SI_COMPOUND_MAP[base_unit_str]
    else:
        unit_key = base_unit_str.split(" ")[0]
        unit_si = _SI_OUTPUT_MAP.get(unit_key, base_unit_str)
    return NormalizedValue(
        value=float(si_quantity.magnitude),
        unit_si=unit_si,
        original=expression,
    )
