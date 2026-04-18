"""Unit tests for composition rules."""
from __future__ import annotations

from services.geometry.composition_rules import COMPOSITION_RULES


def test_flywheel_to_shaft() -> None:
    rule = COMPOSITION_RULES[("Flywheel_Rim", "Shaft")]
    out = rule({"inner_diameter_m": 0.1, "thickness_m": 0.05})
    assert out["diameter_m"] == 0.095
    assert out["length_m"] == 0.15


def test_flywheel_to_bearing() -> None:
    rule = COMPOSITION_RULES[("Flywheel_Rim", "Bearing_Housing")]
    out = rule({"inner_diameter_m": 0.1, "thickness_m": 0.05})
    assert out["bore_diameter_m"] > 0.095
    assert out["outer_diameter_m"] > out["bore_diameter_m"]


def test_pelton_to_shaft() -> None:
    rule = COMPOSITION_RULES[("Pelton_Runner", "Shaft")]
    out = rule({"runner_diameter_m": 0.8})
    assert out["diameter_m"] == 0.8 * 0.15
    assert out["length_m"] == 0.8 * 1.5


def test_pelton_to_housing() -> None:
    rule = COMPOSITION_RULES[("Pelton_Runner", "Housing")]
    out = rule({"runner_diameter_m": 0.8})
    assert out["inner_diameter_m"] > 0.8
    assert out["wall_thickness_m"] > 0


def test_pelton_to_frame() -> None:
    rule = COMPOSITION_RULES[("Pelton_Runner", "Mounting_Frame")]
    out = rule({"runner_diameter_m": 0.8})
    assert out["length_m"] > 0
    assert out["width_m"] > 0
    assert out["height_m"] > 0


def test_panel_to_tensor() -> None:
    rule = COMPOSITION_RULES[("Hinge_Panel", "Tensor_Rod")]
    out = rule({"height_m": 2.0, "thickness_m": 0.02})
    assert out["length_m"] >= 2.0
    assert out["diameter_m"] > 0


def test_panel_to_connector() -> None:
    rule = COMPOSITION_RULES[("Hinge_Panel", "Base_Connector")]
    out = rule({"height_m": 2.0, "thickness_m": 0.02})
    assert out["width_m"] > 0
    assert out["height_m"] > 0


def test_all_seven_rules_registered() -> None:
    assert len(COMPOSITION_RULES) == 7
