"""Unit tests for DesignIntent and TriStateField."""
from __future__ import annotations

import pytest

from services.interpreter.domain.intent import (
    DesignIntent,
    FieldSource,
    TriStateField,
)


def test_extracted_field_has_value_and_no_reason() -> None:
    f = TriStateField(value=0.5, source=FieldSource.EXTRACTED)
    assert f.value == 0.5
    assert f.source == "extracted"
    assert f.reason is None
    assert f.required is False


def test_defaulted_field_requires_reason() -> None:
    with pytest.raises(ValueError, match="defaulted fields must include a reason"):
        TriStateField(value="steel_a36", source=FieldSource.DEFAULTED)


def test_missing_field_has_null_value_and_required_true() -> None:
    f = TriStateField(value=None, source=FieldSource.MISSING, required=True)
    assert f.value is None
    assert f.source == "missing"
    assert f.required is True


def test_missing_field_with_non_null_value_raises() -> None:
    with pytest.raises(ValueError, match="missing fields must have value=None"):
        TriStateField(value=0.5, source=FieldSource.MISSING, required=True)


def test_design_intent_roundtrip() -> None:
    intent = DesignIntent(
        type="flywheel",
        fields={
            "outer_diameter_m": TriStateField(value=0.5, source=FieldSource.EXTRACTED),
            "inner_diameter_m": TriStateField(
                value=0.1, source=FieldSource.DEFAULTED, reason="common ratio 1:5"
            ),
            "rpm": TriStateField(value=3000, source=FieldSource.EXTRACTED),
            "thickness_m": TriStateField(
                value=None, source=FieldSource.MISSING, required=True
            ),
        },
    )
    data = intent.model_dump()
    restored = DesignIntent.model_validate(data)
    assert restored == intent
