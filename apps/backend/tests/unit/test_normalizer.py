"""Unit tests for the unit normalizer."""
from __future__ import annotations

import pytest

from services.interpreter.domain.errors import ErrorCode, InterpreterException
from services.interpreter.normalizer.units import NormalizedValue, normalize


def test_metric_meters_passthrough() -> None:
    r = normalize("0.5 m")
    assert r == NormalizedValue(value=0.5, unit_si="m", original="0.5 m")


def test_metric_centimeters_to_meters() -> None:
    r = normalize("25 cm")
    assert r.value == pytest.approx(0.25)
    assert r.unit_si == "m"


def test_metric_millimeters_to_meters() -> None:
    r = normalize("50 mm")
    assert r.value == pytest.approx(0.05)


def test_imperial_inches_to_meters() -> None:
    r = normalize("10 inches")
    assert r.value == pytest.approx(0.254)
    assert r.unit_si == "m"


def test_imperial_feet_to_meters() -> None:
    r = normalize("3 ft")
    assert r.value == pytest.approx(0.9144)


def test_imperial_pounds_to_kg() -> None:
    r = normalize("10 lb")
    assert r.value == pytest.approx(4.5359237)
    assert r.unit_si == "kg"


def test_rpm_preserved_as_compound_unit() -> None:
    # RPM is not an SI unit but is a canonical engineering unit we keep as-is.
    r = normalize("3000 rpm")
    assert r.value == 3000.0
    assert r.unit_si == "rpm"


def test_psi_to_pascal() -> None:
    r = normalize("100 psi")
    assert r.value == pytest.approx(689475.7, rel=1e-4)
    assert r.unit_si == "Pa"


def test_pure_number_no_unit_returns_dimensionless() -> None:
    r = normalize("42")
    assert r.value == 42.0
    assert r.unit_si == ""  # dimensionless marker


def test_invalid_unit_raises() -> None:
    with pytest.raises(InterpreterException) as exc:
        normalize("3 platypus")
    assert exc.value.error.code == ErrorCode.UNIT_PARSE_FAILED
