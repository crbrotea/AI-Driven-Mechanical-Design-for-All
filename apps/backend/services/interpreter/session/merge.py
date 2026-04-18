"""Pure functions for merging user overrides into a DesignIntent.

These functions are deterministic and never call external services.
"""
from __future__ import annotations

from typing import Any

from services.interpreter.domain.intent import (
    DesignIntent,
    FieldSource,
    TriStateField,
)


def apply_user_overrides(
    intent: DesignIntent,
    overrides: dict[str, TriStateField],
) -> DesignIntent:
    """Return a new DesignIntent with user overrides applied.

    User overrides always win over LLM-inferred values. The original
    intent is not mutated.
    """
    if not overrides:
        return intent
    new_fields = dict(intent.fields)
    for name, override in overrides.items():
        new_fields[name] = override
    return DesignIntent(
        type=intent.type,
        fields=new_fields,
        composed_of=list(intent.composed_of),
    )


def merge_refinement(
    intent: DesignIntent,
    field_updates: dict[str, Any],
) -> DesignIntent:
    """Apply raw field updates from the refine endpoint.

    Each update is coerced into a TriStateField with source=USER.
    """
    overrides = {
        name: TriStateField(value=value, source=FieldSource.USER)
        for name, value in field_updates.items()
    }
    return apply_user_overrides(intent, overrides)
