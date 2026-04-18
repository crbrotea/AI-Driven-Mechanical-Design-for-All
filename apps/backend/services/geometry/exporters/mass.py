"""Mass properties calculator — volume, mass, CoG, bbox in SI units."""
from __future__ import annotations

from build123d import Compound, Part

from services.geometry.domain.artifacts import MassProperties
from services.interpreter.domain.materials import MaterialProperties


def compute_mass_properties(
    part: Part | Compound,
    material: MaterialProperties,
) -> MassProperties:
    """Compute SI mass properties from a build123d Part/Compound."""
    # build123d internal unit is mm; volume is mm³
    volume_mm3 = part.volume
    volume_m3 = volume_mm3 * 1e-9
    mass_kg = volume_m3 * material.density_kg_m3

    cog = part.center()
    bbox = part.bounding_box()

    return MassProperties(
        volume_m3=volume_m3,
        mass_kg=mass_kg,
        center_of_mass=(cog.X * 1e-3, cog.Y * 1e-3, cog.Z * 1e-3),
        bbox_m=(
            bbox.min.X * 1e-3,
            bbox.min.Y * 1e-3,
            bbox.min.Z * 1e-3,
            bbox.max.X * 1e-3,
            bbox.max.Y * 1e-3,
            bbox.max.Z * 1e-3,
        ),
    )
