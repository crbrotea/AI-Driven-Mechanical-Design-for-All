"""In-memory cache for S5 Documenter keyed by intent + analysis + narrative."""
from __future__ import annotations

import hashlib
import json
import math

from services.documenter.domain.models import Deliverables
from services.explainer.domain.models import NaturalReport
from services.interpreter.domain.intent import DesignIntent
from services.physics.domain.models import AnalysisResult


class DocumenterCache:
    def __init__(self) -> None:
        self._store: dict[str, Deliverables] = {}

    @staticmethod
    def key_for(
        intent: DesignIntent,
        analysis: AnalysisResult,
        narrative: NaturalReport,
    ) -> str:
        sf = analysis.safety_factor
        sf_canonical: str | float = round(sf, 6) if math.isfinite(sf) else "inf"
        canonical = {
            "intent_type": intent.type,
            "intent_fields": {
                k: f.value
                for k, f in sorted(intent.fields.items())
                if f.value is not None
            },
            "stress_max_pa": round(analysis.stress_max_pa, 6),
            "safety_factor": sf_canonical,
            "verdict": analysis.verdict.value,
            "material": analysis.material_name,
            "narrative_facts": sorted(narrative.facts_used),
            "summary_hash": hashlib.sha256(
                narrative.summary.encode("utf-8")
            ).hexdigest()[:8],
        }
        payload = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]

    def get(self, key: str) -> Deliverables | None:
        return self._store.get(key)

    def put(self, key: str, value: Deliverables) -> None:
        self._store[key] = value

    def clear(self) -> None:
        self._store.clear()
