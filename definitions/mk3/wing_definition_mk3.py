"""Demo 2.0 **mk3**: mk2 rebuilt in the omega construction.

Same planform, airfoil, rods, joint fits and 5/3/1/1 ladder as
``../mk2/wing_definition_mk2.py``, and the same requested rod positions. What
changes is how the rods are held:

    mk2  bore    rod centre skin_distance + r = 3.75 mm under the skin, in a
                 printed tube, bell modifier around it
    mk3  omega   rod tangent to the inside of the skin (0.45 mm wall, the
                 sleeve thickness, so a straight rod clears the joint too),
                 held by a one-line omega clip whose feet sit on the skin

Consequences that are layout, not analysis:

  * The root span is the master and is placed exactly as requested.
  * Every outboard rod is snapped to 0.5 mm beside the nearest inboard rod
    (surface to surface), so the two share one clip through the lap and
    the lap bond is as short as the geometry allows. The printed layout
    report says where each rod went and why.
  * Front and rear webs at x/c 0.20 and 0.70 close a torsion box, one line
    thick. LE cell, box cell and TE cell are separate modifiers so each can
    carry its own infill.
  * Lap modifiers shrink to a capsule over both rods at 1.2 x diameter.

None of mk2's structural numbers (EI, failure g, wall shear) have been rerun
for this layout. The rods sit further from the neutral axis, so rod EI goes
up, but the load path into them is now the skin and a 0.42 mm clip instead
of a bore and a bell. Treat mk3 as untested until it is.
"""
from wing_assembler import WingDefinition, RodSection, OmegaSettings


SPAN = 800.0
ROOT_CHORD = 200.0
TIP_CHORD = 160.0
ROD_LENGTH = 250.0
N_ROD_SPANS = 4
L_EFF = SPAN / N_ROD_SPANS

# mk2's requested positions, unchanged. The half-pitch parity trick that kept
# mk2's spans clear of each other is moot here: the omega solver snaps
# outboard rods beside inboard ones instead of keeping them apart.
X_MID = (0.35 - 0.5) * ROOT_CHORD       # -30.0 mm
HALF_PITCH = 6.52
_LATTICE = {
    0: [-4, -2, 0, 2, 4],                # five pairs, x/c 0.220-0.480
    1: [-3, -1, 1],                      # three pairs
    2: [0],                              # one pair
    3: [-1],                             # one pair
}


def _chord_at_span_start(r: int) -> float:
    t = r * L_EFF / SPAN
    return ROOT_CHORD + (TIP_CHORD - ROOT_CHORD) * t


def _pcts(r: int) -> list[float]:
    """Convert the absolute-x lattice for span ``r`` to chord fractions."""
    c = _chord_at_span_start(r)
    return [(X_MID + HALF_PITCH * j) / c + 0.5 for j in _LATTICE[r]]


wing = WingDefinition(
    span=SPAN,                         # semi-span panel; full wing = 1600 mm
    root_chord=ROOT_CHORD,
    tip_chord=TIP_CHORD,
    naca="4412",
    rod_length=ROD_LENGTH,             # 20 actual 3 mm carbon rods
    rod_multiple=1,                    # one print section per 200 mm rod span
    rod_overlap_pct=0.10,              # 25 mm rod engagement at each handover
    rod_diameter=3.5,                  # 3 mm rod in the 3.5 mm fit envelope
    skin_distance=2.0,                 # unused by omega
    joint_length=15.0,
    joint_thickness=0.45,
    clearance=0.0,
    epoxy_gap=0.3,
    axial_gap=0.3,
    rod_sections=[
        RodSection(chord_pcts=_pcts(0)),
        RodSection(chord_pcts=_pcts(1)),
        RodSection(chord_pcts=_pcts(2)),
        RodSection(chord_pcts=_pcts(3)),
    ],
    construction="omega",
    omega=OmegaSettings(
        line_width=0.42,
        skin_lines=1,
        omega_lines=1,
        omega_clearance=0.0,
        omega_neck_width=None,         # = rod_diameter: clip legs leave the skin straight up
        omega_foot_length=1.0,
        rod_min_gap=0.5,
        snap_to_previous=True,
        joint_mod_margin_pct=0.20,
        box_le_pct=0.20,
        box_te_pct=0.30,
        box_wall_lines=1,
    ),
)
