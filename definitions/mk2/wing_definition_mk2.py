"""Demo 2.0 **mk2**: NACA 4412, 800 mm semi-span, 200 -> 160 mm chord, 5/3/1/1.

Same planform, same 20 rods, same lattice pitch as ``../wing_definition_4321.py`` (mk1).
The only change is how the 10 pairs are spent down the span, and it is worth
having: the peak rod stress sits at the ROOT (117.6 MPa at n=1 against 46 MPa at
the first joint), so pairs spent outboard are pairs spent where nothing is
asking for them.

    (WL 100, uniform lift, n=1; recomputed 2026-09-08 -- the previous line
     quoted 139.5/117.6 MPa and 3.15/3.74 g, which no current driver produces)

    mk1  4/3/2/1   EI root 0.406e9   rod compr 134.9 MPa   first failure 3.26 g
    mk2  5/3/1/1   EI root 0.502e9   rod compr 113.0 MPa   first failure 3.78 g

    +24 % root EI and +16 % on the load that breaks it, for zero extra material.
    But see below: mk2's 3.78 g is a WALL mode, not a rod mode, so the re-split
    buys its margin in the rod ladder (4.59/5.16 g against mk1's 3.84/4.32) and
    the two wings tie on first failure.
    All 26 splits of 10 pairs over 4 spans were run; 5/3/1/1 wins, and it wins
    because the moment is 4x higher at the root than it is at the first lap
    while the rod count was only 1.33x higher.

Why the root band is NOT re-centred on maximum section depth
    Pair separation peaks at x/c 0.294 on this section, and for the mk1's FOUR
    pairs (a 39 mm band) centring there was worth ~5 % of EI. It does not carry
    over to five. Five pairs at the 13.04 mm same-span pitch is a 52 mm band =
    26 % of chord, and d(x/c) is asymmetric — it falls away faster forward of
    0.294 than aft of it. Centring the group on 0.294 drives the forward rod out
    to x/c 0.154 where the 4412 is shallow, and costs more than the centring
    gains: 3.62 g against 3.74 g. So the group stays centred on x/c 0.35 and
    runs 0.220-0.480. **The optimum group centroid is aft of the optimum single
    rod.** Checked, not assumed.

Spans 2 and 3 carry one pair each and do not govern anything, so they are placed
on maximum depth (x/c 0.333 and 0.285, d = 12.83 and 11.78 mm) — the tie-break
is pair separation, because those rods have no neighbour to share with.

What governs mk2, after `tests/experiment-01` and `-02` (2026-09-08)
    The ladder at WL 100 (28.8 kg), ELLIPTICAL lift — `load_matrix.py` runs
    uniform, 1.18x heavier at the root, which shifts every line down ~18 %:

        3.78 g  printed wall in SHEAR. Jourawski on the cut where tau peaks,
                against `sigma_wall(R)` at that cut's FLATTEST crossing
                (R = 534 mm -> 13.2 MPa). Governs.
        3.80 g  rod -> BARE bore, if the bell were dropped (measured floor,
                tests/experiment-02). With the bell it is 8.18 g
        5.16 g  rod compression, beam on an elastic foundation (494 MPa, Vesic;
                439.8 by the transferred-k route -> 4.59 g)
        5.40 g  printed wall in COMPRESSION at the crown, R = 215 mm — face
                wrinkling into the 5 % infill at 13.2 MPa. Still an estimate
        6.26 g  rod material at 600 MPa (tension side is >= 1500)
        9.20 g  rod-rod lap bond
       22.64 g  printed wall in shear IF the whole cut earned its most-curved
                crossing (R = 3.55 mm). An upper bracket, NOT an allowable

    An intermediate revision of this docstring claimed 5.16 g by taking that
    last line as the allowable. It is not: `tests/experiment-01` earned the
    curvature term on an ELLIPSE, whose y=0 cut crosses two equally tight
    strips. A 4412 cut crosses the nose at R = 3.5 mm and the aft lower skin at
    R = 534 mm, both at the same tau, so the flat one governs. First failure is
    **3.78 g**, a shell mode, and mk1 sits on the same number — the 5/3/1/1
    re-split buys margin in the ROD modes (4.59/5.16 g against mk1's 3.84/4.32)
    and nothing in the shell.

    Three things that must not be quietly dropped:

      * **The bell modifier stays — because mk2 is at WL 100.** Without it the
        rod sheds 21.7 N/mm at 7 g into bare 5 % infill. `tests/experiment-02`
        measured that path directly (12 kgf on 10 mm, held) and puts a floor of
        tau >= 0.72 MPa on it, worth **3.8 g** here — level with the wall-shear
        mode, and by a floor rather than a strength. At the reference set's
        16 kgf/m^2 the same floor gives >= 23 g and the bell would be optional.
        It is a wing-loading requirement, not a construction requirement.
        Note the bell does not lower the stress: its 10 mm mouth is narrower
        than the bore's 16.3 mm circumference, so tau goes UP 1.6x. It wins on
        the material it hands to (40 % fill, not 5 %), so the strong lever is
        the bell's density, not its width.
      * **The lap EDGE is the critical station**, not the lap. Rod area steps
        down while the moment has barely fallen, so the stress jumps by the area
        ratio. This is where `experiment-01` broke.
      * **The wall-shear number is the softest in the model** and it governs.
        See `../../../LEARNINGS.md` §10 item 0.

Torsion is unchanged by construction. `GJ = G 4 A_m^2 / (ds/t)` has no boom term,
so the rod layout cannot move it: 3.36e7 N.mm2, EI/GJ = 14.9 against 1-3 for a
conventional wing. See `torsion.py`. The rods barely move the shear centre
either — **0.247c against 0.283c bare**, not the 0.135c an earlier revision
claimed; that number was two bugs in `torsion._shear_flow`, both fixed and both
now covered by `tests/test_solvers.py`. The elastic axis therefore sits
essentially ON the AC, so this wing is NOT comfortably divergence-free, and a
chordwise-uniform sandbag acts 34 mm aft of the shear centre for 34 N.m of root
torque at 7 g against a 38 N.m wall limit — 89 %, not the 1.6x over that was
reported. Strap the load at x/c 0.247 anyway.

Everything else — planform, lattice origin, half-pitch, parity rule, print
settings — is carried over unchanged from mk1, which documents them.
"""
from wing_assembler import WingDefinition, RodSection


SPAN = 800.0
ROOT_CHORD = 200.0
TIP_CHORD = 160.0
ROD_LENGTH = 250.0
N_ROD_SPANS = 4
L_EFF = SPAN / N_ROD_SPANS

# Same absolute-x lattice as mk1: one origin for the whole wing, even j on even
# spans and odd j on odd, so the 6.30 mm collision rule keeps 0.22 mm of slack
# where two spans coexist in the lap.
X_MID = (0.35 - 0.5) * ROOT_CHORD       # -30.0 mm
HALF_PITCH = 6.52                        # > 3.5 * (1 + 0.8) = 6.30 mm
_LATTICE = {
    0: [-4, -2, 0, 2, 4],                # five pairs, even parity, x/c 0.220-0.480
    1: [-3, -1, 1],                      # three pairs, odd parity
    2: [0],                              # one pair, even parity, on max depth
    3: [-1],                             # one pair, odd parity, on max depth
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
    rod_length=ROD_LENGTH,             # 20 actual 3 mm carbon rods, 2.6 g each
    rod_multiple=1,                    # one print section per 200 mm rod span
    rod_overlap_pct=0.10,              # 25 mm rod engagement at each handover
    rod_diameter=3.5,                  # 3 mm rod in the 3.5 mm bore/fit envelope
    skin_distance=2.0,
    joint_length=15.0,
    joint_thickness=0.45,
    clearance=0.0,
    epoxy_gap=0.3,
    axial_gap=0.3,
    rod_sections=[
        RodSection(chord_pcts=_pcts(0)),  # 10 rods, c=200 mm, d = 14.4-15.2 mm
        RodSection(chord_pcts=_pcts(1)),  # 6 rods,  c=190 mm, d = 13.6-14.1 mm
        RodSection(chord_pcts=_pcts(2)),  # 2 rods,  c=180 mm, d = 12.8 mm
        RodSection(chord_pcts=_pcts(3)),  # 2 rods,  c=170 mm, d = 11.8 mm
    ],
    min_x_separation_pct=0.25,
    min_y_separation_pct=0.8,            # 6.30 mm collision threshold
    bell_width=10.0,
    bell_height=7.0,
    bell_offset=-1.5,
    bell_shape=3.5,
    joint_mod_thickness=12.0,
)
