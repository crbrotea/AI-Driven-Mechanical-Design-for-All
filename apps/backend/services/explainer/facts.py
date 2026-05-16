"""Build the FACTS table fed to Gemma for grounded narration."""
from __future__ import annotations

from services.interpreter.domain.intent import DesignIntent
from services.physics.domain.models import AnalysisResult


def build_facts(intent: DesignIntent, result: AnalysisResult) -> dict[str, str]:
    """Return a flat dict {label: formatted_value} fed to Gemma.

    Every number Gemma is allowed to cite MUST be present here. If a value
    is not here, Gemma must NOT invent it.
    """
    facts: dict[str, str] = {
        "intent_type": intent.type,
        "material_name": result.material_name,
        "material_yield_mpa": f"{result.material_yield_mpa:.1f} MPa",
        "formula": result.formula,
        "stress_max_mpa": f"{result.stress_max_pa / 1e6:.2f} MPa",
        "displacement_max_mm": f"{result.displacement_max_m * 1e3:.3f} mm",
        "safety_factor": f"{result.safety_factor:.2f}",
        "verdict": result.verdict.value.upper(),
    }
    for k, v in result.inputs.items():
        facts[f"input.{k}"] = f"{v:.3f}"
    for name, field in intent.fields.items():
        if field.value is not None:
            facts[f"intent.{name}"] = f"{field.value}"
    return facts
