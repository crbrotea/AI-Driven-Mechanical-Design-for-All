"""Shelter solver - wind-loaded cantilever bending of a single panel.

Governing formulas (per unit width, cantilever model):
    v          = wind_speed_m_s
    q_dyn      = 0.5 * rho_air * v^2
    P          = C_p * q_dyn                     (C_p = 0.8 plate drag)
    sigma_max  = 6 * P * L^2 / (2 * t^2)         (cantilever bending)
    delta_max  = P * L^4 / (8 * E * t^3)
    SF         = yield / sigma_max
"""
from __future__ import annotations

import math

from services.interpreter.domain.materials import MaterialProperties
from services.physics.domain.errors import AnalysisError, AnalysisErrorCode
from services.physics.domain.models import AnalysisResult, LoadCase, classify_verdict

_DRAG_COEFFICIENT = 0.8
_FORMULA = "sigma = 6*P*L^2/t^2 (cantilever bending, wind load)"


def solve_shelter(
    geometry: dict[str, float],
    load_case: LoadCase,
    material: MaterialProperties,
) -> AnalysisResult:
    height = float(geometry["height_m"])
    thickness = float(geometry["thickness_m"])
    wind = float(load_case.values["wind_speed_m_s"])
    rho_air = float(load_case.values.get("air_density_kg_m3", 1.225))

    if thickness <= 0:
        AnalysisError(
            code=AnalysisErrorCode.NUMERICAL_OVERFLOW,
            message=f"thickness_m must be > 0, got {thickness}",
            intent_type="Hinge_Panel",
            field="thickness_m",
        ).raise_as()

    q_dyn = 0.5 * rho_air * wind * wind
    pressure = _DRAG_COEFFICIENT * q_dyn
    young_pa = material.young_modulus_gpa * 1.0e9
    yield_pa = material.yield_strength_mpa * 1.0e6

    if pressure == 0.0:
        sigma_max = 0.0
        displacement = 0.0
        safety_factor = math.inf
    else:
        sigma_max = 6.0 * pressure * height * height / (2.0 * thickness * thickness)
        displacement = pressure * (height**4) / (8.0 * young_pa * thickness**3)
        safety_factor = yield_pa / sigma_max

    return AnalysisResult(
        intent_type="Hinge_Panel",
        material_name=material.name,
        material_yield_mpa=material.yield_strength_mpa,
        formula=_FORMULA,
        stress_max_pa=sigma_max,
        displacement_max_m=displacement,
        safety_factor=safety_factor,
        inputs={
            "wind_speed_m_s": wind,
            "air_density_kg_m3": rho_air,
            "pressure_pa": pressure,
            "height_m": height,
            "thickness_m": thickness,
        },
        verdict=classify_verdict(safety_factor),
        notes="cantilever bending per unit width; C_p = 0.8 (plate drag)",
    )
