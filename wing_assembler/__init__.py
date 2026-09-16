"""wing_assembler — definition in, printable wing STLs out.

A wing is described once as a `WingDefinition` (planform, airfoil, rod ladder,
joint fits).  `compute_section_layout` turns that into print sections with rod
bores placed and collisions resolved; `build_all` turns each section into solid
geometry; `generate.run` writes the STLs.

    from wing_assembler import WingDefinition, RodSection

Rod placement is the point: the reinforcement sits just under the skin rather
than on the neutral axis, so the definition carries a per-span rod ladder
(`rod_sections`) instead of a single spar.
"""

from .naca import (
    fits_inside,
    naca4_polygon_pts,
    naca4_y_at,
    naca4_y_lower_at,
    offset_polygon,
    rod_y_lower,
    rod_y_upper,
)
from .section_layout import (
    ComputedRod,
    OmegaSettings,
    PhysicalRodSection,
    RodSection,
    SectionInfo,
    SectionJointMod,
    SectionRodHole,
    WingDefinition,
    chord_at,
    compute_section_layout,
    print_layout,
)
from .topopt_modifier import (
    TopOptPatch,
    build_topopt_modifier,
    default_patches,
    extract_patches_from_density,
)
from .wing_builder import build_all

__version__ = "0.1.0"

__all__ = [
    # definition
    "WingDefinition",
    "RodSection",
    "OmegaSettings",
    # layout
    "compute_section_layout",
    "print_layout",
    "chord_at",
    "SectionInfo",
    "SectionRodHole",
    "SectionJointMod",
    "ComputedRod",
    "PhysicalRodSection",
    # geometry
    "build_all",
    # topopt
    "TopOptPatch",
    "build_topopt_modifier",
    "default_patches",
    "extract_patches_from_density",
    # airfoil
    "naca4_polygon_pts",
    "naca4_y_at",
    "naca4_y_lower_at",
    "offset_polygon",
    "rod_y_upper",
    "rod_y_lower",
    "fits_inside",
    "__version__",
]
