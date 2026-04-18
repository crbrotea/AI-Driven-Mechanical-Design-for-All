"""Unit tests for session intent merging."""
from __future__ import annotations

from services.interpreter.domain.intent import (
    DesignIntent,
    FieldSource,
    TriStateField,
)
from services.interpreter.session.merge import apply_user_overrides, merge_refinement


def _f(value: object, source: FieldSource = FieldSource.EXTRACTED) -> TriStateField:
    return TriStateField(value=value, source=source)


def test_user_override_wins_over_extracted() -> None:
    intent = DesignIntent(
        type="Flywheel_Rim",
        fields={"outer_diameter_m": _f(0.5)},
    )
    overrides = {
        "outer_diameter_m": TriStateField(value=0.8, source=FieldSource.USER)
    }
    merged = apply_user_overrides(intent, overrides)
    assert merged.fields["outer_diameter_m"].value == 0.8
    assert merged.fields["outer_diameter_m"].source == FieldSource.USER


def test_override_fills_missing_field() -> None:
    intent = DesignIntent(
        type="Flywheel_Rim",
        fields={
            "outer_diameter_m": _f(0.5),
            "inner_diameter_m": TriStateField(
                value=None, source=FieldSource.MISSING, required=True
            ),
        },
    )
    overrides = {
        "inner_diameter_m": TriStateField(value=0.1, source=FieldSource.USER)
    }
    merged = apply_user_overrides(intent, overrides)
    assert merged.fields["inner_diameter_m"].value == 0.1
    assert merged.fields["inner_diameter_m"].source == FieldSource.USER
    assert not merged.has_missing_fields()


def test_no_overrides_returns_same_intent() -> None:
    intent = DesignIntent(
        type="Shaft", fields={"diameter_m": _f(0.05), "length_m": _f(0.5)}
    )
    merged = apply_user_overrides(intent, {})
    assert merged == intent


def test_merge_refinement_applies_field_updates_as_user_source() -> None:
    intent = DesignIntent(
        type="Shaft", fields={"diameter_m": _f(0.05), "length_m": _f(0.5)}
    )
    updated = merge_refinement(intent, {"diameter_m": 0.08})
    assert updated.fields["diameter_m"].value == 0.08
    assert updated.fields["diameter_m"].source == FieldSource.USER
    # Unchanged field preserved.
    assert updated.fields["length_m"].value == 0.5


def test_merge_refinement_unknown_field_creates_user_entry() -> None:
    # If the user form sends a field not in the intent, we add it.
    intent = DesignIntent(
        type="Shaft", fields={"diameter_m": _f(0.05), "length_m": _f(0.5)}
    )
    updated = merge_refinement(intent, {"material": "steel_a36"})
    assert updated.fields["material"].value == "steel_a36"
    assert updated.fields["material"].source == FieldSource.USER


def test_apply_user_overrides_is_immutable() -> None:
    intent = DesignIntent(type="Shaft", fields={"diameter_m": _f(0.05)})
    overrides = {
        "diameter_m": TriStateField(value=0.08, source=FieldSource.USER)
    }
    merged = apply_user_overrides(intent, overrides)
    # Original intent is untouched.
    assert intent.fields["diameter_m"].value == 0.05
    assert merged.fields["diameter_m"].value == 0.08
