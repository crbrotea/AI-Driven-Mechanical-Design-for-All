"""solve_flywheel - analytical centrifugal stress check."""
from __future__ import annotations

import math

import pytest

from services.interpreter.domain.materials import MaterialProperties
from services.physics.domain.models import LoadCase, Verdict
from services.physics.solvers.flywheel import solve_flywheel

_STEEL_A36 = MaterialProperties(
    name="steel_a36",
    display_name="Steel A36",
    category="metal",
    density_kg_m3=7850.0,
    young_modulus_gpa=200.0,
    yield_strength_mpa=250.0,
    ultimate_tensile_strength_mpa=400.0,
    thermal_conductivity_w_m_k=51.0,
    max_service_temperature_c=400.0,
    relative_cost_index=1.0,
    sustainability_score=0.5,
)


def test_flywheel_stress_matches_analytical_within_5pct() -> None:
    """sigma = rho*omega^2*R^2 for canonical inputs (steel A36, 3000 rpm, R=0.5)."""
    omega = 2 * math.pi * 3000.0 / 60.0
    sigma_theory = 7850.0 * omega**2 * 0.5**2
    lc = LoadCase(intent_type="Flywheel_Rim", values={"angular_velocity_rad_s": omega})
    result = solve_flywheel(
        geometry={"outer_diameter_m": 1.0, "inner_diameter_m": 0.4, "thickness_m": 0.05},
        load_case=lc,
        material=_STEEL_A36,
    )
    rel_err = abs(result.stress_max_pa - sigma_theory) / sigma_theory
    assert rel_err < 0.05, f"theory={sigma_theory:.3e}, got={result.stress_max_pa:.3e}"


def test_flywheel_zero_rpm_returns_zero_stress() -> None:
    lc = LoadCase(intent_type="Flywheel_Rim", values={"angular_velocity_rad_s": 0.0})
    result = solve_flywheel(
        geometry={"outer_diameter_m": 1.0, "inner_diameter_m": 0.4, "thickness_m": 0.05},
        load_case=lc,
        material=_STEEL_A36,
    )
    assert result.stress_max_pa == pytest.approx(0.0)
    assert math.isinf(result.safety_factor)
    assert result.verdict is Verdict.PASS


def test_flywheel_canonical_hero_lands_in_warn() -> None:
    """Hero #1 (outer_diameter=0.5 m, 3000 rpm, steel A36) lands above SF=1."""
    omega = 2 * math.pi * 3000.0 / 60.0
    lc = LoadCase(intent_type="Flywheel_Rim", values={"angular_velocity_rad_s": omega})
    result = solve_flywheel(
        geometry={"outer_diameter_m": 0.5, "inner_diameter_m": 0.1, "thickness_m": 0.05},
        load_case=lc,
        material=_STEEL_A36,
    )
    assert result.safety_factor > 1.0
    assert result.verdict in {Verdict.PASS, Verdict.WARN}
    assert "rho*omega" in result.formula or "rho" in result.formula
    assert result.inputs["angular_velocity_rad_s"] == pytest.approx(omega)


def test_flywheel_overspeed_triggers_fail() -> None:
    omega = 2 * math.pi * 12000.0 / 60.0  # 12 000 rpm - way past steel A36 yield
    lc = LoadCase(intent_type="Flywheel_Rim", values={"angular_velocity_rad_s": omega})
    result = solve_flywheel(
        geometry={"outer_diameter_m": 1.0, "inner_diameter_m": 0.4, "thickness_m": 0.05},
        load_case=lc,
        material=_STEEL_A36,
    )
    assert result.verdict is Verdict.FAIL
    assert result.safety_factor < 1.5
