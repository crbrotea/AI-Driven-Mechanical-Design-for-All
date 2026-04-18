"""Pelton_Runner primitive builder (simplified).

Represented as a disk with simplified bucket pockets as cylindrical cavities
around the periphery. Sufficient for visualization and mass estimation.
"""
from __future__ import annotations

import math

from build123d import Cylinder, Location, Part, Vector


def build_pelton_runner(
    runner_diameter_m: float,
    bucket_count: int,
) -> Part:
    """Build a simplified Pelton turbine runner.

    Args:
        runner_diameter_m: Outer diameter of the runner disk.
        bucket_count: Number of bucket pockets around the periphery (12-30 valid).
    """
    if runner_diameter_m <= 0:
        raise ValueError(f"runner_diameter must be positive, got {runner_diameter_m}")
    if not (12 <= bucket_count <= 30):
        raise ValueError(f"bucket_count must be in [12, 30], got {bucket_count}")

    disk_thickness_mm = runner_diameter_m * 0.1 * 1000.0
    disk_radius_mm = (runner_diameter_m / 2) * 1000.0
    bucket_radius_mm = disk_radius_mm * 0.12  # ~12% of runner radius

    disk = Cylinder(radius=disk_radius_mm, height=disk_thickness_mm)

    # Subtract bucket pockets around the periphery
    bucket_ring_radius_mm = disk_radius_mm * 0.85
    for i in range(bucket_count):
        angle = 2 * math.pi * i / bucket_count
        x = bucket_ring_radius_mm * math.cos(angle)
        y = bucket_ring_radius_mm * math.sin(angle)
        bucket = Cylinder(
            radius=bucket_radius_mm, height=disk_thickness_mm * 1.1
        ).locate(Location(Vector(x, y, 0)))
        disk = disk - bucket

    return disk
