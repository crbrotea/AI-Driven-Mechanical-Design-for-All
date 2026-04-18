"""Unit tests for the builders registry."""
from __future__ import annotations

import pytest

from services.geometry.builders import BUILDERS, get_builder
from services.geometry.domain.errors import GeometryErrorCode, GeometryException


def test_all_seven_primitives_registered() -> None:
    assert set(BUILDERS.keys()) == {
        "Flywheel_Rim", "Shaft", "Bearing_Housing",
        "Pelton_Runner", "Housing", "Mounting_Frame", "Hinge_Panel",
    }


def test_get_builder_returns_callable() -> None:
    builder = get_builder("Shaft")
    part = builder(diameter_m=0.05, length_m=0.5)
    assert part.volume > 0


def test_get_unknown_raises_geometry_exception() -> None:
    with pytest.raises(GeometryException) as exc:
        get_builder("NonExistent_Primitive")
    assert exc.value.error.code == GeometryErrorCode.UNKNOWN_PRIMITIVE
