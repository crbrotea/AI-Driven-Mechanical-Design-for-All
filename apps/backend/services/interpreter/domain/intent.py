"""DesignIntent and TriStateField — the output contract of the Interpreter."""
from __future__ import annotations

from enum import StrEnum
from typing import Any, Self

from pydantic import BaseModel, ConfigDict, model_validator


class FieldSource(StrEnum):
    """Origin of a field value in a DesignIntent."""

    EXTRACTED = "extracted"  # LLM parsed it from user input
    DEFAULTED = "defaulted"  # LLM inferred a reasonable default
    MISSING = "missing"      # LLM could not determine; user must fill
    USER = "user"            # User explicitly set this via the form


class TriStateField(BaseModel):
    """A single field of a DesignIntent with provenance metadata."""

    model_config = ConfigDict(frozen=True)

    value: Any | None
    source: FieldSource
    reason: str | None = None
    required: bool = False
    original: str | None = None  # preserves user's original unit expression

    @model_validator(mode="after")
    def _validate_source_constraints(self) -> Self:
        if self.source == FieldSource.DEFAULTED and not self.reason:
            raise ValueError("defaulted fields must include a reason")
        if self.source == FieldSource.MISSING and self.value is not None:
            raise ValueError("missing fields must have value=None")
        return self


class DesignIntent(BaseModel):
    """The output of the Interpreter: a fully typed design specification."""

    model_config = ConfigDict(frozen=False)

    type: str                          # primitive name, e.g. "flywheel"
    fields: dict[str, TriStateField]
    composed_of: list[str] = []        # names of additional primitives composed

    def has_missing_fields(self) -> bool:
        return any(f.source == FieldSource.MISSING for f in self.fields.values())

    def missing_field_names(self) -> list[str]:
        return [
            name for name, f in self.fields.items()
            if f.source == FieldSource.MISSING
        ]
