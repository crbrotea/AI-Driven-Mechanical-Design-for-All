"""Flywheel solver - closed-form centrifugal stress for a thin rim.

Governing formula:
    sigma_max = rho * omega^2 * R_outer^2     [Pa]   (thin-rim centrifugal stress)
    delta_radial = sigma_max * R_outer / E    [m]
    SF = yield_strength / sigma_max

Assumptions: thin rim (t << R), uniform density, axisymmetric, steady-state.
Conservative upper bound on stress for hollow disks.
"""
from __future__ import annotations

import math

from services.interpreter.domain.materials import MaterialProperties
from services.physics.domain.errors import AnalysisError, AnalysisErrorCode
from services.physics.domain.models import AnalysisResult, LoadCase, classify_verdict

_FORMULA = "sigma = rho*omega^2*R^2 (thin-rim centrifugal)"


def solve_flywheel(
    geometry: dict[str, float],
    load_case: LoadCase,
    material: MaterialProperties,
) -> AnalysisResult:
    try:
        outer_diameter_m = float(geometry["outer_diameter_m"])
        omega = float(load_case.values["angular_velocity_rad_s"])
    except KeyError as e:  # pragma: no cover - defended by load_case derivation
        AnalysisError(
            code=AnalysisErrorCode.MISSING_GEOMETRY_FIELD,
            message=f"missing key: {e!r}",
            intent_type="Flywheel_Rim",
        ).raise_as()
        raise AssertionError("unreachable") from None  # for type checker

    radius_outer = outer_diameter_m / 2.0
    rho = material.density_kg_m3
    young_pa = material.young_modulus_gpa * 1.0e9
    yield_pa = material.yield_strength_mpa * 1.0e6

    sigma_max = rho * omega * omega * radius_outer * radius_outer
    if sigma_max == 0.0:
        safety_factor = math.inf
        displacement = 0.0
    else:
        safety_factor = yield_pa / sigma_max
        displacement = sigma_max * radius_outer / young_pa

    return AnalysisResult(
        intent_type="Flywheel_Rim",
        material_name=material.name,
        material_yield_mpa=material.yield_strength_mpa,
        formula=_FORMULA,
        stress_max_pa=sigma_max,
        displacement_max_m=displacement,
        safety_factor=safety_factor,
        verdict=classify_verdict(safety_factor),
        inputs={
            "angular_velocity_rad_s": omega,
            "outer_diameter_m": outer_diameter_m,
        },
        notes="thin-rim approximation; valid when thickness << outer radius",
    )
