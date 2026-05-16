"""project_views tests."""
from __future__ import annotations

from services.documenter.views import project_views
from services.geometry.composer import compose_assembly
from services.interpreter.domain.intent import DesignIntent, FieldSource, TriStateField


def _flywheel_intent() -> DesignIntent:
    return DesignIntent(
        type="Flywheel_Rim",
        fields={
            "outer_diameter_m": TriStateField(value=0.5, source=FieldSource.EXTRACTED),
            "inner_diameter_m": TriStateField(value=0.1, source=FieldSource.EXTRACTED),
            "thickness_m": TriStateField(value=0.05, source=FieldSource.EXTRACTED),
        },
        composed_of=[],
    )


def test_project_views_returns_three_view_keys() -> None:
    compound = compose_assembly(_flywheel_intent())
    views = project_views(compound)
    assert set(views.keys()) == {"front", "side", "iso"}


def test_project_views_returns_svg_bytes() -> None:
    compound = compose_assembly(_flywheel_intent())
    views = project_views(compound)
    for name, svg in views.items():
        assert isinstance(svg, bytes), name
        head = svg.lstrip()[:64]
        assert head.startswith(b"<?xml") or head.startswith(b"<svg"), (name, head[:30])


def test_project_views_front_and_side_differ() -> None:
    compound = compose_assembly(_flywheel_intent())
    views = project_views(compound)
    assert views["front"] != views["side"]


def test_project_views_iso_falls_back_to_top_when_iso_export_fails(monkeypatch) -> None:
    from services.documenter import views as views_module

    real_export = views_module._export_svg
    fail_count = {"n": 0}

    def fake_export(compound, view_vector):
        if tuple(view_vector) == (1, 1, 1) and fail_count["n"] == 0:
            fail_count["n"] += 1
            raise RuntimeError("simulated iso projection failure")
        return real_export(compound, view_vector)

    monkeypatch.setattr(views_module, "_export_svg", fake_export)
    compound = compose_assembly(_flywheel_intent())
    views = project_views(compound)
    assert "iso" in views
    assert views["iso"].lstrip().startswith(b"<?xml") or views["iso"].lstrip().startswith(b"<svg")
