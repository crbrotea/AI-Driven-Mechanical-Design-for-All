"""Hydro solver - Pelton runner torque and shaft torsion shear.

Governing formulas:
    v_jet       = sqrt(2 * g * H)
    u_optimal   = 0.46 * v_jet                       (Pelton design rule)
    omega       = u_optimal / R_runner
    P_hyd       = rho_water * g * Q * H * eta        (eta = 0.85)
    T           = P_hyd / omega
    d_shaft     = D_runner * 0.15                    (S2 composition rule)
    tau_shear   = 16 * T / (pi * d_shaft^3)
    SF          = (yield / sqrt(3)) / tau_shear      (von Mises shear allowable)
"""
from __future__ import annotations

import math

from services.interpreter.domain.materials import MaterialProperties
from services.physics.domain.errors import AnalysisError, AnalysisErrorCode
from services.physics.domain.models import AnalysisResult, LoadCase, classify_verdict

_GRAVITY_M_S2 = 9.81
_WATER_DENSITY_KG_M3 = 1000.0
_SHAFT_DIAMETER_RATIO = 0.15   # from services/geometry/composition_rules.py:_pelton_to_shaft
_PELTON_UJET_RATIO = 0.46
_FORMULA = "tau = 16T/(pi*d^3), T = P_hyd/omega, P_hyd = rho_w*g*Q*H*eta"


def solve_hydro(
    geometry: dict[str, float],
    load_case: LoadCase,
    material: MaterialProperties,
) -> AnalysisResult:
    runner_d = float(geometry["runner_diameter_m"])
    head = float(load_case.values["head_m"])
    flow = float(load_case.values["flow_m3_s"])
    efficiency = float(load_case.values.get("efficiency", 0.85))

    if runner_d <= 0:
        AnalysisError(
            code=AnalysisErrorCode.NUMERICAL_OVERFLOW,
            message=f"runner_diameter_m must be > 0, got {runner_d}",
            intent_type="Pelton_Runner",
            field="runner_diameter_m",
        ).raise_as()

    runner_radius = runner_d / 2.0
    v_jet = math.sqrt(2.0 * _GRAVITY_M_S2 * head) if head > 0 else 0.0
    u_optimal = _PELTON_UJET_RATIO * v_jet
    omega = u_optimal / runner_radius if u_optimal > 0 else 0.0
    p_hyd = _WATER_DENSITY_KG_M3 * _GRAVITY_M_S2 * flow * head * efficiency

    if omega == 0.0 or p_hyd == 0.0:
        torque = 0.0
        tau_shear = 0.0
        safety_factor = math.inf
        displacement = 0.0
    else:
        torque = p_hyd / omega
        d_shaft = runner_d * _SHAFT_DIAMETER_RATIO
        tau_shear = 16.0 * torque / (math.pi * d_shaft**3)
        yield_pa = material.yield_strength_mpa * 1.0e6
        allowable_shear = yield_pa / math.sqrt(3.0)
        safety_factor = allowable_shear / tau_shear
        young_pa = material.young_modulus_gpa * 1.0e9
        shear_modulus = young_pa / (2.0 * (1.0 + 0.3))
        polar_j = math.pi * d_shaft**4 / 32.0
        theta = torque * (runner_d * 1.5) / (shear_modulus * polar_j)
        displacement = theta * runner_radius

    return AnalysisResult(
        intent_type="Pelton_Runner",
        material_name=material.name,
        material_yield_mpa=material.yield_strength_mpa,
        formula=_FORMULA,
        stress_max_pa=tau_shear,
        displacement_max_m=displacement,
        safety_factor=safety_factor,
        verdict=classify_verdict(safety_factor),
        inputs={
            "head_m": head,
            "flow_m3_s": flow,
            "efficiency": efficiency,
            "runner_diameter_m": runner_d,
            "shaft_torque_n_m": torque,
            "angular_velocity_rad_s": omega,
        },
        notes=(
            "von Mises shear allowable; "
            "shaft diameter from S2 composition rule (0.15 * D_runner)"
        ),
    )
