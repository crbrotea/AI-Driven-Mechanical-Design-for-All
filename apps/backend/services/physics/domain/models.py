"""Domain models for S3 Physics — LoadCase, AnalysisResult, Verdict."""
from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class Verdict(StrEnum):
    """Classification of a design's safety margin."""

    PASS = "pass"   # safety_factor >= 2.0
    WARN = "warn"   # 1.5 <= safety_factor < 2.0
    FAIL = "fail"   # safety_factor < 1.5


def classify_verdict(safety_factor: float) -> Verdict:
    """Map a numeric safety factor to a Verdict label."""
    if safety_factor >= 2.0:
        return Verdict.PASS
    if safety_factor >= 1.5:
        return Verdict.WARN
    return Verdict.FAIL


class LoadCase(BaseModel):
    """Derived physical load conditions for a single intent."""

    model_config = ConfigDict(frozen=True)

    intent_type: str
    values: dict[str, float] = Field(default_factory=dict)


class AnalysisResult(BaseModel):
    """Result of an analytical structural check for a single intent."""

    intent_type: str
    material_name: str
    material_yield_mpa: float
    formula: str
    stress_max_pa: float
    displacement_max_m: float
    safety_factor: float
    verdict: Verdict
    inputs: dict[str, float] = Field(default_factory=dict)
    notes: str | None = None
    extras: dict[str, Any] | None = None
