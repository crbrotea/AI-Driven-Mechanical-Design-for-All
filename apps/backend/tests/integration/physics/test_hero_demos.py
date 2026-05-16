"""End-to-end S3 integration over the three hero demos."""
from __future__ import annotations

import pytest


@pytest.mark.integration
def test_hero_flywheel_500kj_3000rpm(physics_client, hero_intents) -> None:
    material, intent = hero_intents["hero_flywheel_500kj_3000rpm"]
    r = physics_client.post(
        "/analyze",
        json={"intent": intent.model_dump(), "material_name": material},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["verdict"] in {"pass", "warn"}
    assert body["safety_factor"] >= 1.2
    assert "rho" in body["formula"].lower() or "omega" in body["formula"].lower()


@pytest.mark.integration
def test_hero_hydro_5cms_20m(physics_client, hero_intents) -> None:
    material, intent = hero_intents["hero_hydro_5cms_20m"]
    r = physics_client.post(
        "/analyze",
        json={"intent": intent.model_dump(), "material_name": material},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["verdict"] in {"pass", "warn"}
    assert body["safety_factor"] >= 1.5


@pytest.mark.integration
def test_hero_shelter_4p_100kmh(physics_client, hero_intents) -> None:
    material, intent = hero_intents["hero_shelter_4p_100kmh"]
    r = physics_client.post(
        "/analyze",
        json={"intent": intent.model_dump(), "material_name": material},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["verdict"] in {"pass", "warn"}
    assert body["safety_factor"] >= 1.2
