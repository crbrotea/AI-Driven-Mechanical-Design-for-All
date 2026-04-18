"""Unit tests for mass properties calculator."""
from __future__ import annotations

import math

import pytest

from services.geometry.exporters.mass import compute_mass_properties
from services.geometry.primitives.flywheel_rim import build_flywheel_rim
from services.interpreter.domain.materials import MaterialProperties


def _steel() -> MaterialProperties:
    return MaterialProperties(
        name="steel_a36",
        display_name="Steel A36",
        category="metal",
        density_kg_m3=7850,
        young_modulus_gpa=200,
        yield_strength_mpa=250,
        ultimate_tensile_strength_mpa=400,
        thermal_conductivity_w_m_k=51,
        max_service_temperature_c=400,
        relative_cost_index=1.0,
        sustainability_score=0.5,
    )


def test_flywheel_mass_matches_analytical() -> None:
    part = build_flywheel_rim(0.5, 0.1, 0.05)
    mass = compute_mass_properties(part, _steel())
    expected_v_m3 = math.pi / 4 * (0.5**2 - 0.1**2) * 0.05
    expected_m_kg = expected_v_m3 * 7850
    assert mass.mass_kg == pytest.approx(expected_m_kg, rel=0.05)


def test_bbox_has_six_values() -> None:
    part = build_flywheel_rim(0.5, 0.1, 0.05)
    mass = compute_mass_properties(part, _steel())
    assert len(mass.bbox_m) == 6
    # min < max for each axis
    assert mass.bbox_m[0] < mass.bbox_m[3]
    assert mass.bbox_m[1] < mass.bbox_m[4]
    assert mass.bbox_m[2] < mass.bbox_m[5]


def test_mass_properties_in_si() -> None:
    part = build_flywheel_rim(0.5, 0.1, 0.05)
    mass = compute_mass_properties(part, _steel())
    # volume in m³ should be O(0.01)
    assert 0.001 < mass.volume_m3 < 0.1
