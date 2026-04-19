"""Demo fallback — serves pre-generated hero demos from local disk.

Used when GCS is unavailable during the live demo. The three hero
intents have fixed canonical hashes baked in at deploy time.
"""
from __future__ import annotations

from pathlib import Path

from services.geometry.domain.artifacts import CachedArtifacts, MassProperties

# Hashes computed from canonical hero intents via compute_intent_hash().
# Regenerate whenever the hero intent definitions change (should be rare).
DEMO_INTENT_HASHES: dict[str, str] = {
    "hero_flywheel_500kj_3000rpm": "c03a446d17fc0fd5",
    "hero_hydro_5cms_20m": "10f365e8a14cb72f",
    "hero_shelter_4p_100kmh": "3adb6a2a7c405856",
}


DEFAULT_FALLBACK_BASE = Path("/app/data/demo_artifacts")


async def lookup_demo_fallback(
    intent_hash: str, *, base_dir: Path = DEFAULT_FALLBACK_BASE
) -> CachedArtifacts | None:
    """Return demo artifacts from disk if the hash is a known hero and files exist."""
    if intent_hash not in DEMO_INTENT_HASHES.values():
        return None

    dir_ = base_dir / intent_hash
    if not dir_.exists() or not dir_.is_dir():
        return None

    mass_file = dir_ / "mass.json"
    if not mass_file.exists():
        return None

    try:
        mass = MassProperties.model_validate_json(mass_file.read_text())
    except Exception:
        return None

    # Return relative proxy URLs — the frontend prepends the API base URL.
    # The /generate/demo_artifact/{hash}/{filename} endpoint streams bytes from disk.
    return CachedArtifacts(
        mass_properties=mass,
        step_url=f"/generate/demo_artifact/{intent_hash}/geometry.step",
        glb_url=f"/generate/demo_artifact/{intent_hash}/geometry.glb",
        svg_url=f"/generate/demo_artifact/{intent_hash}/section.svg",
    )
