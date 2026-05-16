"""solve_shelter - wind-loaded cantilever panel bending."""
from __future__ import annotations

import math

import pytest

from services.interpreter.domain.materials import MaterialProperties
from services.physics.domain.models import LoadCase, Verdict
from services.physics.solvers.shelter import solve_shelter

_BAMBOO = MaterialProperties(
    name="bamboo_laminated",
    display_name="Bamboo Laminated",
    category="composite",
    density_kg_m3=700.0,
    young_modulus_gpa=12.0,
    yield_strength_mpa=60.0,
    ultimate_tensile_strength_mpa=80.0,
    thermal_conductivity_w_m_k=0.2,
    max_service_temperature_c=80.0,
    relative_cost_index=0.6,
    sustainability_score=0.95,
)


def test_shelter_pressure_matches_drag_formula() -> None:
    wind_m_s = 100.0 / 3.6
    q_dyn = 0.5 * 1.225 * wind_m_s**2
    p_expected = 0.8 * q_dyn
    lc = LoadCase(
        intent_type="Hinge_Panel",
        values={"wind_speed_m_s": wind_m_s, "air_density_kg_m3": 1.225},
    )
    result = solve_shelter(
        geometry={"width_m": 1.0, "height_m": 2.0, "thickness_m": 0.02},
        load_case=lc,
        material=_BAMBOO,
    )
    assert math.isclose(result.inputs["pressure_pa"], p_expected, rel_tol=1e-6)


def test_shelter_zero_wind_returns_zero_stress() -> None:
    lc = LoadCase(
        intent_type="Hinge_Panel",
        values={"wind_speed_m_s": 0.0, "air_density_kg_m3": 1.225},
    )
    result = solve_shelter(
        geometry={"width_m": 1.0, "height_m": 2.0, "thickness_m": 0.02},
        load_case=lc,
        material=_BAMBOO,
    )
    assert result.stress_max_pa == pytest.approx(0.0)
    assert math.isinf(result.safety_factor)
    assert result.verdict is Verdict.PASS


def test_shelter_canonical_hero_returns_finite_sf() -> None:
    """100 km/h on a 1x2x0.02 m bamboo panel - bamboo is near limit by design."""
    lc = LoadCase(
        intent_type="Hinge_Panel",
        values={"wind_speed_m_s": 100.0 / 3.6, "air_density_kg_m3": 1.225},
    )
    result = solve_shelter(
        geometry={"width_m": 1.0, "height_m": 2.0, "thickness_m": 0.02},
        load_case=lc,
        material=_BAMBOO,
    )
    assert result.safety_factor > 0
    assert "PL" in result.formula or "P*L" in result.formula


def test_shelter_hurricane_fails() -> None:
    lc = LoadCase(
        intent_type="Hinge_Panel",
        values={"wind_speed_m_s": 300.0 / 3.6, "air_density_kg_m3": 1.225},
    )
    result = solve_shelter(
        geometry={"width_m": 1.0, "height_m": 2.0, "thickness_m": 0.005},
        load_case=lc,
        material=_BAMBOO,
    )
    assert result.verdict is Verdict.FAIL
