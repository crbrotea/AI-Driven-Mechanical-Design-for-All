"""In-memory cache for the explainer keyed by intent + analysis values."""
from __future__ import annotations

import hashlib
import json
import math

from services.explainer.domain.models import NaturalReport
from services.interpreter.domain.intent import DesignIntent
from services.physics.domain.models import AnalysisResult


class ExplainerCache:
    def __init__(self) -> None:
        self._store: dict[str, NaturalReport] = {}

    @staticmethod
    def key_for(intent: DesignIntent, result: AnalysisResult) -> str:
        # safety_factor may be math.inf for zero-load cases; json.dumps would
        # reject that, so store as string when not finite.
        sf_canonical: str | float
        if math.isfinite(result.safety_factor):
            sf_canonical = round(result.safety_factor, 6)
        else:
            sf_canonical = "inf"
        canonical = {
            "intent_type": intent.type,
            "intent_fields": {
                k: f.value
                for k, f in sorted(intent.fields.items())
                if f.value is not None
            },
            "stress_max_pa": round(result.stress_max_pa, 6),
            "safety_factor": sf_canonical,
            "verdict": result.verdict.value,
            "material": result.material_name,
        }
        payload = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]

    def get(self, key: str) -> NaturalReport | None:
        return self._store.get(key)

    def put(self, key: str, report: NaturalReport) -> None:
        self._store[key] = report

    def clear(self) -> None:
        self._store.clear()
