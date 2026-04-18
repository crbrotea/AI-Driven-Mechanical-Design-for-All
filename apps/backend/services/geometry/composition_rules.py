"""Hardcoded composition rules for known (main, composed) pairs.

Each rule maps the main primitive's numeric parameter dict to the
composed primitive's parameter dict. Purely functional, no side effects.
"""
from __future__ import annotations

from collections.abc import Callable

CompositionRule = Callable[[dict[str, float]], dict[str, float]]


def _flywheel_to_shaft(flywheel: dict[str, float]) -> dict[str, float]:
    return {
        "diameter_m": flywheel["inner_diameter_m"] * 0.95,
        "length_m": round(flywheel["thickness_m"] * 3.0, 10),
    }


def _flywheel_to_bearing(flywheel: dict[str, float]) -> dict[str, float]:
    shaft_d = flywheel["inner_diameter_m"] * 0.95
    return {
        "bore_diameter_m": shaft_d * 1.01,
        "outer_diameter_m": shaft_d * 2.5,
    }


def _pelton_to_shaft(pelton: dict[str, float]) -> dict[str, float]:
    d = pelton["runner_diameter_m"]
    return {"diameter_m": d * 0.15, "length_m": d * 1.5}


def _pelton_to_housing(pelton: dict[str, float]) -> dict[str, float]:
    return {
        "inner_diameter_m": pelton["runner_diameter_m"] * 1.3,
        "wall_thickness_m": 0.01,
    }


def _pelton_to_frame(pelton: dict[str, float]) -> dict[str, float]:
    d = pelton["runner_diameter_m"]
    return {"length_m": d * 2.0, "width_m": d * 1.6, "height_m": 0.1}


def _panel_to_tensor(panel: dict[str, float]) -> dict[str, float]:
    return {
        "length_m": panel["height_m"] * 1.1,
        "diameter_m": 0.01,
    }


def _panel_to_connector(panel: dict[str, float]) -> dict[str, float]:
    return {
        "width_m": panel["thickness_m"] * 2,
        "height_m": 0.02,
    }


COMPOSITION_RULES: dict[tuple[str, str], CompositionRule] = {
    ("Flywheel_Rim", "Shaft"): _flywheel_to_shaft,
    ("Flywheel_Rim", "Bearing_Housing"): _flywheel_to_bearing,
    ("Pelton_Runner", "Shaft"): _pelton_to_shaft,
    ("Pelton_Runner", "Housing"): _pelton_to_housing,
    ("Pelton_Runner", "Mounting_Frame"): _pelton_to_frame,
    ("Hinge_Panel", "Tensor_Rod"): _panel_to_tensor,
    ("Hinge_Panel", "Base_Connector"): _panel_to_connector,
}
