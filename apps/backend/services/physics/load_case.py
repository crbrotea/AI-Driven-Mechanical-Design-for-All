"""LoadCase derivation: DesignIntent -> LoadCase per hero type."""
from __future__ import annotations

import math
from collections.abc import Callable

from services.interpreter.domain.intent import DesignIntent, FieldSource, TriStateField
from services.physics.domain.errors import AnalysisError, AnalysisErrorCode
from services.physics.domain.models import LoadCase

_AIR_DENSITY_KG_M3 = 1.225
_PELTON_EFFICIENCY = 0.85

_GEOMETRY_REQUIRED: dict[str, tuple[str, ...]] = {
    "Flywheel_Rim": ("outer_diameter_m", "inner_diameter_m", "thickness_m"),
    "Pelton_Runner": ("runner_diameter_m", "bucket_count"),
    "Hinge_Panel": ("width_m", "height_m", "thickness_m"),
}

_LOAD_REQUIRED: dict[str, tuple[str, ...]] = {
    "Flywheel_Rim": ("rpm",),
    "Pelton_Runner": ("head_m", "flow_m3_s"),
    "Hinge_Panel": ("wind_kmh",),
}


def _present(field: TriStateField | None) -> bool:
    return field is not None and field.source is not FieldSource.MISSING and field.value is not None


def _require_geometry(intent: DesignIntent) -> None:
    for name in _GEOMETRY_REQUIRED[intent.type]:
        if not _present(intent.fields.get(name)):
            AnalysisError(
                code=AnalysisErrorCode.MISSING_GEOMETRY_FIELD,
                message=f"{name} is required for {intent.type}",
                intent_type=intent.type,
                field=name,
            ).raise_as()


def _require_load(intent: DesignIntent) -> None:
    for name in _LOAD_REQUIRED[intent.type]:
        if not _present(intent.fields.get(name)):
            AnalysisError(
                code=AnalysisErrorCode.MISSING_LOAD_PARAMETER,
                message=f"{name} is required for {intent.type}",
                intent_type=intent.type,
                field=name,
            ).raise_as()


def _val(intent: DesignIntent, name: str) -> float:
    f = intent.fields[name]
    assert f.value is not None  # _require_* enforces presence
    return float(f.value)


def _check_positive(intent_type: str, name: str, value: float) -> None:
    if value <= 0:
        AnalysisError(
            code=AnalysisErrorCode.INVALID_LOAD_VALUE,
            message=f"{name} must be > 0, got {value}",
            intent_type=intent_type,
            field=name,
        ).raise_as()


def _flywheel(intent: DesignIntent) -> LoadCase:
    _require_geometry(intent)
    _require_load(intent)
    rpm = _val(intent, "rpm")
    _check_positive(intent.type, "rpm", rpm)
    omega = 2 * math.pi * rpm / 60.0
    return LoadCase(intent_type=intent.type, values={"angular_velocity_rad_s": omega})


def _hydro(intent: DesignIntent) -> LoadCase:
    _require_geometry(intent)
    _require_load(intent)
    head = _val(intent, "head_m")
    flow = _val(intent, "flow_m3_s")
    _check_positive(intent.type, "head_m", head)
    _check_positive(intent.type, "flow_m3_s", flow)
    return LoadCase(
        intent_type=intent.type,
        values={"head_m": head, "flow_m3_s": flow, "efficiency": _PELTON_EFFICIENCY},
    )


def _shelter(intent: DesignIntent) -> LoadCase:
    _require_geometry(intent)
    _require_load(intent)
    wind_kmh = _val(intent, "wind_kmh")
    if wind_kmh < 0:
        AnalysisError(
            code=AnalysisErrorCode.INVALID_LOAD_VALUE,
            message=f"wind_kmh must be >= 0, got {wind_kmh}",
            intent_type=intent.type,
            field="wind_kmh",
        ).raise_as()
    return LoadCase(
        intent_type=intent.type,
        values={
            "wind_speed_m_s": wind_kmh / 3.6,
            "air_density_kg_m3": _AIR_DENSITY_KG_M3,
        },
    )


_DERIVERS: dict[str, Callable[[DesignIntent], LoadCase]] = {
    "Flywheel_Rim": _flywheel,
    "Pelton_Runner": _hydro,
    "Hinge_Panel": _shelter,
}


def derive_load_case(intent: DesignIntent) -> LoadCase:
    """Derive a LoadCase from a DesignIntent. Raises AnalysisException on errors."""
    deriver = _DERIVERS.get(intent.type)
    if deriver is None:
        AnalysisError(
            code=AnalysisErrorCode.UNSUPPORTED_INTENT_TYPE,
            message=f"No analysis available for intent.type={intent.type!r}",
            intent_type=intent.type,
        ).raise_as()
        raise AssertionError("unreachable")  # for type checker
    return deriver(intent)
