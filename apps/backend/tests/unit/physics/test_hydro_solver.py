"""solve_hydro - Pelton runner torque + shaft torsion check."""
from __future__ import annotations

import math

import pytest

from services.interpreter.domain.materials import MaterialProperties
from services.physics.domain.models import LoadCase, Verdict
from services.physics.solvers.hydro import solve_hydro

_STAINLESS_304 = MaterialProperties(
    name="stainless_304",
    display_name="Stainless 304",
    category="metal",
    density_kg_m3=8000.0,
    young_modulus_gpa=193.0,
    yield_strength_mpa=215.0,
    ultimate_tensile_strength_mpa=505.0,
    thermal_conductivity_w_m_k=16.0,
    max_service_temperature_c=800.0,
    relative_cost_index=2.5,
    sustainability_score=0.6,
)


def test_hydro_torque_matches_power_over_omega() -> None:
    head = 20.0
    flow = 0.5
    runner_d = 0.8
    g = 9.81
    rho_water = 1000.0
    efficiency = 0.85
    v_jet = math.sqrt(2 * g * head)
    u = 0.46 * v_jet
    omega = u / (runner_d / 2.0)
    p_hyd = rho_water * g * flow * head * efficiency
    torque_theory = p_hyd / omega

    lc = LoadCase(
        intent_type="Pelton_Runner",
        values={"head_m": head, "flow_m3_s": flow, "efficiency": efficiency},
    )
    result = solve_hydro(
        geometry={"runner_diameter_m": runner_d, "bucket_count": 20.0},
        load_case=lc,
        material=_STAINLESS_304,
    )
    assert math.isclose(result.inputs["shaft_torque_n_m"], torque_theory, rel_tol=1e-6)


def test_hydro_canonical_hero_passes() -> None:
    lc = LoadCase(
        intent_type="Pelton_Runner",
        values={"head_m": 20.0, "flow_m3_s": 0.5, "efficiency": 0.85},
    )
    result = solve_hydro(
        geometry={"runner_diameter_m": 0.8, "bucket_count": 20.0},
        load_case=lc,
        material=_STAINLESS_304,
    )
    assert result.safety_factor > 1.5
    assert result.verdict in {Verdict.PASS, Verdict.WARN}
    assert "T/" in result.formula


def test_hydro_zero_flow_returns_zero_stress() -> None:
    lc = LoadCase(
        intent_type="Pelton_Runner",
        values={"head_m": 20.0, "flow_m3_s": 0.0, "efficiency": 0.85},
    )
    result = solve_hydro(
        geometry={"runner_diameter_m": 0.8, "bucket_count": 20.0},
        load_case=lc,
        material=_STAINLESS_304,
    )
    assert result.stress_max_pa == pytest.approx(0.0)
    assert result.verdict is Verdict.PASS


def test_hydro_huge_head_triggers_fail() -> None:
    lc = LoadCase(
        intent_type="Pelton_Runner",
        values={"head_m": 2000.0, "flow_m3_s": 10.0, "efficiency": 0.85},
    )
    result = solve_hydro(
        geometry={"runner_diameter_m": 0.05, "bucket_count": 20.0},  # small shaft
        load_case=lc,
        material=_STAINLESS_304,
    )
    assert result.verdict is Verdict.FAIL
