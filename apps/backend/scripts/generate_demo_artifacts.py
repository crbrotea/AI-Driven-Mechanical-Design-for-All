"""One-shot: populate apps/backend/data/demo_artifacts/{hash}/ for all heroes.

Run ONCE locally (with build123d installed) before deploying:

    cd apps/backend && uv run python scripts/generate_demo_artifacts.py
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Ensure services/ is on sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.geometry.cache import compute_intent_hash
from services.geometry.composer import compose_assembly
from services.geometry.exporters.glb import export_glb
from services.geometry.exporters.mass import compute_mass_properties
from services.geometry.exporters.step import export_step
from services.geometry.exporters.svg import export_svg
from services.geometry.fallback import DEMO_INTENT_HASHES
from services.interpreter.domain.intent import DesignIntent, FieldSource, TriStateField
from services.interpreter.domain.materials import load_catalog

ROOT = Path(__file__).parent.parent
OUT_ROOT = ROOT / "data" / "demo_artifacts"


def _f(v: object) -> TriStateField:
    return TriStateField(value=v, source=FieldSource.EXTRACTED)


HERO_INTENTS = [
    (
        "hero_flywheel_500kj_3000rpm",
        "steel_a36",
        DesignIntent(
            type="Flywheel_Rim",
            fields={
                "outer_diameter_m": _f(0.5),
                "inner_diameter_m": _f(0.1),
                "thickness_m": _f(0.05),
                "rpm": _f(3000),
            },
            composed_of=["Shaft", "Bearing_Housing"],
        ),
    ),
    (
        "hero_hydro_5cms_20m",
        "stainless_304",
        DesignIntent(
            type="Pelton_Runner",
            fields={"runner_diameter_m": _f(0.8), "bucket_count": _f(20)},
            composed_of=["Shaft", "Housing", "Mounting_Frame"],
        ),
    ),
    (
        "hero_shelter_4p_100kmh",
        "bamboo_laminated",
        DesignIntent(
            type="Hinge_Panel",
            fields={"width_m": _f(1.0), "height_m": _f(2.0), "thickness_m": _f(0.02)},
            composed_of=["Tensor_Rod", "Base_Connector"],
        ),
    ),
]


async def main() -> None:
    catalog = load_catalog(ROOT / "data" / "materials.json")

    for label, material_name, intent in HERO_INTENTS:
        intent_hash = compute_intent_hash(intent)
        expected = DEMO_INTENT_HASHES[label]
        if intent_hash != expected:
            print(
                f"[WARN] hash mismatch for {label}: "
                f"computed {intent_hash}, expected {expected}"
            )

        out_dir = OUT_ROOT / intent_hash
        out_dir.mkdir(parents=True, exist_ok=True)

        material = catalog.get(material_name)
        print(f"Building {label} (hash={intent_hash})...")

        compound = compose_assembly(intent)
        export_step(compound, out_dir / "geometry.step")
        export_glb(compound, out_dir / "geometry.glb")
        export_svg(compound, out_dir / "section.svg")
        mass = compute_mass_properties(compound, material)
        (out_dir / "mass.json").write_text(mass.model_dump_json())

        print(f"  -> {out_dir}")

    print("Done. Verify with:")
    print(f"  ls -lh {OUT_ROOT}/*/")


if __name__ == "__main__":
    asyncio.run(main())
