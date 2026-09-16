"""Topology-optimization modifier volumes for wing sections."""
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from build123d import Compound, Location, Solid, Vector

from .naca import naca4_y_at, naca4_y_lower_at
from .section_layout import SectionInfo, WingDefinition, chord_at


@dataclass
class TopOptPatch:
    """A chordwise infill densification patch derived from topology optimization."""
    x_frac_start: float
    x_frac_end: float
    name: str = ""
    infill_density: float = 40.0
    extra_walls: int = 0


def extract_patches_from_density(
    density_path: str | Path,
    chord: float = 300.0,
    threshold: float = 0.30,
    min_width_frac: float = 0.02,
) -> list[TopOptPatch]:
    """
    Load a topopt density .npy file and extract chordwise patches.

    The density array has shape (nx, ny, nz) where:
    - axis 0 = chordwise (0=LE, 1=TE)
    - axis 1 = thickness (y)
    - axis 2 = spanwise (z)

    The profile is averaged over thickness and span, thresholded into
    contiguous high-density zones, and filtered by minimum chordwise width.
    Patch infill density is linearly mapped from 0.3->20% through 0.5->40%,
    0.7->60%, and 1.0->100%.
    """
    density = np.asarray(np.load(Path(density_path)), dtype=float)
    if density.ndim != 3:
        raise ValueError(f"Expected a 3D density array, got shape {density.shape}")

    profile = density.mean(axis=(1, 2))
    nx = profile.size
    if nx == 0:
        return []

    high_density = profile >= threshold
    patches = []
    zone_start = None

    for index in range(nx + 1):
        in_zone = index < nx and bool(high_density[index])
        if in_zone and zone_start is None:
            zone_start = index
        elif not in_zone and zone_start is not None:
            zone_end = index
            width_mm = (zone_end - zone_start) * chord / nx
            if width_mm >= min_width_frac * chord:
                mean_density = float(profile[zone_start:zone_end].mean())
                infill_density = float(np.interp(
                    mean_density,
                    [0.3, 0.5, 0.7, 1.0],
                    [20.0, 40.0, 60.0, 100.0],
                ))
                patches.append(TopOptPatch(
                    x_frac_start=zone_start / nx,
                    x_frac_end=zone_end / nx,
                    name=f"topopt_patch_{len(patches) + 1}",
                    infill_density=infill_density,
                ))
            zone_start = None

    return patches


def default_patches() -> list[TopOptPatch]:
    """Return the hardcoded patches from the h=6mm vf=0.20 topopt run.

    These are the two-patch pattern (LE + mid-chord) that was robust across
    all ablation tests (isotropic, no-wall, buckling).
    """
    return [
        TopOptPatch(
            x_frac_start=0.04, x_frac_end=0.16,
            name="LE_patch",
            infill_density=40.0,
            extra_walls=2,
        ),
        TopOptPatch(
            x_frac_start=0.51, x_frac_end=0.59,
            name="mid_chord_patch",
            infill_density=40.0,
            extra_walls=2,
        ),
    ]


def build_topopt_modifier(
    sec: SectionInfo,
    wing: WingDefinition,
    patches: list[TopOptPatch] | None = None,
    wall_inset: float = 1.5,
) -> list:
    """
    Build modifier box solids for the topopt-identified patches.

    For each patch, a box is placed at centered chordwise coordinates, with its
    height set by the thinnest airfoil section across the patch after applying
    wall_inset. The box spans the full local section length from z=0 to z=L.
    """
    if patches is None:
        patches = default_patches()
    if not patches:
        return []

    chord = chord_at(sec.z_start, wing)
    depth = sec.z_end - sec.z_start
    solids = []

    for patch in patches:
        x_start = patch.x_frac_start * chord - chord / 2
        x_end = patch.x_frac_end * chord - chord / 2
        x_samples = np.linspace(patch.x_frac_start, patch.x_frac_end, 25)
        upper_surface = min(
            naca4_y_at(wing.naca, float(x_frac)) * chord
            for x_frac in x_samples
        )
        lower_surface = max(
            naca4_y_lower_at(wing.naca, float(x_frac)) * chord
            for x_frac in x_samples
        )
        y_start = lower_surface + wall_inset
        height = upper_surface - wall_inset - y_start

        if x_end <= x_start or height <= 0 or depth <= 0:
            continue

        solids.append(Solid.make_box(x_end - x_start, height, depth).move(
            Location(Vector(x_start, y_start, 0.0))
        ))

    return solids


def add_topopt_to_build_all(
    build_result: dict,
    sec: SectionInfo,
    wing: WingDefinition,
    patches: list[TopOptPatch] | None = None,
) -> dict:
    """
    Add the topopt_modifier Compound to an existing build_all result dict.

    The modifier value is None when no patches produce geometry.
    """
    if patches is None:
        patches = default_patches()
    solids = build_topopt_modifier(sec, wing, patches)
    build_result["topopt_modifier"] = Compound(children=solids) if solids else None
    return build_result
