"""build_facts tests."""
from __future__ import annotations

from services.explainer.facts import build_facts
from services.interpreter.domain.intent import DesignIntent, FieldSource, TriStateField
from services.physics.domain.models import AnalysisResult, Verdict


def _intent_flywheel() -> DesignIntent:
    return DesignIntent(
        type="Flywheel_Rim",
        fields={
            "outer_diameter_m": TriStateField(value=0.5, source=FieldSource.EXTRACTED),
            "inner_diameter_m": TriStateField(value=0.1, source=FieldSource.EXTRACTED),
            "rpm": TriStateField(value=3000.0, source=FieldSource.EXTRACTED),
        },
        composed_of=[],
    )


def _result_flywheel() -> AnalysisResult:
    return AnalysisResult(
        intent_type="Flywheel_Rim",
        material_name="steel_a36",
        material_yield_mpa=250.0,
        formula="sigma = rho*omega^2*R^2",
        stress_max_pa=193.7e6,
        displacement_max_m=4.8e-4,
        safety_factor=1.29,
        verdict=Verdict.WARN,
        inputs={"angular_velocity_rad_s": 314.159, "outer_diameter_m": 0.5},
    )


def test_facts_includes_all_core_outputs() -> None:
    facts = build_facts(_intent_flywheel(), _result_flywheel())
    assert facts["intent_type"] == "Flywheel_Rim"
    assert facts["material_name"] == "steel_a36"
    assert facts["material_yield_mpa"] == "250.0 MPa"
    assert facts["stress_max_mpa"] == "193.70 MPa"
    assert facts["displacement_max_mm"] == "0.480 mm"
    assert facts["safety_factor"] == "1.29"
    assert facts["verdict"] == "WARN"
    assert facts["formula"] == "sigma = rho*omega^2*R^2"


def test_facts_includes_solver_inputs_with_prefix() -> None:
    facts = build_facts(_intent_flywheel(), _result_flywheel())
    assert "input.angular_velocity_rad_s" in facts
    assert facts["input.angular_velocity_rad_s"] == "314.159"


def test_facts_includes_intent_fields_with_prefix() -> None:
    facts = build_facts(_intent_flywheel(), _result_flywheel())
    assert facts["intent.outer_diameter_m"] == "0.5"
    assert facts["intent.inner_diameter_m"] == "0.1"
    assert facts["intent.rpm"] == "3000.0"


def test_facts_skips_intent_field_with_none_value() -> None:
    intent = DesignIntent(
        type="Flywheel_Rim",
        fields={
            "outer_diameter_m": TriStateField(value=0.5, source=FieldSource.EXTRACTED),
            "head_m": TriStateField(value=None, source=FieldSource.MISSING),
        },
        composed_of=[],
    )
    facts = build_facts(intent, _result_flywheel())
    assert "intent.outer_diameter_m" in facts
    assert "intent.head_m" not in facts


def test_facts_verdict_is_uppercased() -> None:
    result = _result_flywheel()
    facts = build_facts(_intent_flywheel(), result)
    assert facts["verdict"] == result.verdict.value.upper()
