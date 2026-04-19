"""Registry mapping primitive names to their builder functions."""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from build123d import Part

from services.geometry.domain.errors import GeometryError, GeometryErrorCode
from services.geometry.primitives.base_connector import build_base_connector
from services.geometry.primitives.bearing_housing import build_bearing_housing
from services.geometry.primitives.flywheel_rim import build_flywheel_rim
from services.geometry.primitives.hinge_panel import build_hinge_panel
from services.geometry.primitives.housing import build_housing
from services.geometry.primitives.mounting_frame import build_mounting_frame
from services.geometry.primitives.pelton_runner import build_pelton_runner
from services.geometry.primitives.shaft import build_shaft
from services.geometry.primitives.tensor_rod import build_tensor_rod

BUILDERS: dict[str, Callable[..., Part]] = {
    "Flywheel_Rim": build_flywheel_rim,
    "Shaft": build_shaft,
    "Bearing_Housing": build_bearing_housing,
    "Pelton_Runner": build_pelton_runner,
    "Housing": build_housing,
    "Mounting_Frame": build_mounting_frame,
    "Hinge_Panel": build_hinge_panel,
    "Tensor_Rod": build_tensor_rod,
    "Base_Connector": build_base_connector,
}


def get_builder(name: str) -> Callable[..., Any]:
    """Return the builder callable for the primitive `name`.

    Raises GeometryException(UNKNOWN_PRIMITIVE) if unregistered.
    """
    if name not in BUILDERS:
        GeometryError(
            code=GeometryErrorCode.UNKNOWN_PRIMITIVE,
            message=f"Primitive '{name}' is not registered.",
            primitive=name,
        ).raise_as()
    return BUILDERS[name]
