# wing_assembler

Definition in, printable wing STLs out.

## Install

```bash
pip install -e .
```

## Use

Write a definition — a `.py` exposing a module-level `wing`:

```python
from wing_assembler import WingDefinition, RodSection

wing = WingDefinition(
    span=800.0, root_chord=200.0, tip_chord=160.0, naca="4412",
    rod_length=250.0, rod_multiple=1, rod_overlap_pct=0.10,
    rod_diameter=3.4, skin_distance=2.0,
    joint_length=15.0, joint_thickness=0.45,
    clearance=0.0, epoxy_gap=0.3, axial_gap=0.3,
    rod_sections=[                       # the rod ladder, root -> tip
        RodSection(chord_pcts=[0.33, 0.285, 0.375, 0.30, 0.35]),
        RodSection(chord_pcts=[0.348, 0.302, 0.32]),
        RodSection(chord_pcts=[0.34]),
        RodSection(chord_pcts=[0.31]),
    ],
    min_x_separation_pct=0.25, min_y_separation_pct=0.8,
    bell_width=10.0, bell_height=7.0, bell_offset=-1.5, bell_shape=3.5,
    joint_mod_thickness=12.0,
)
```

Each `chord_pcts` entry is an **upper + a lower rod** — one pair, at that
fraction of chord. 

To generate the models:

```bash
wing-assembler path/to/wing_definition.py            # -> path/to/output/
wing-assembler path/to/def.py --out /tmp/w --sections 0,1
```

Per print section it writes:

| file | what |
|---|---|
| `section_NN_part.stl` | the part to print |
| `section_NN_bell_modifier.stl` | infill modifier around full-run bores |
| `section_NN_rod_joint_modifier.stl` | infill modifier across each rod lap |
| `section_NN_sleeve_modifier.stl` | infill modifier in the sleeve zone (female sections) |

The three `*_modifier` STLs are **OrcaSlicer modifier volumes, not parts**.
Load them onto the matching `_part.stl` to raise infill locally. Do not print
them.

## Omega construction

`construction="omega"` is a second way to hold the rods. Every rod pair is
placed tangent to the inside of the skin, and each rod is held by an
omega-shaped wall (one line) with feet on the skin. This shape may bring resamblance to a stringer, in traditional wing structures.

Then, spanwise front and rear webs close a torsion box (although, slightly larger than what a traditional torsion box looks like).

```python
from wing_assembler import WingDefinition, RodSection, OmegaSettings

wing = WingDefinition(
    ...,                                   # as above
    construction="omega",
    omega=OmegaSettings(
        line_width=0.42,                   # every wall is a multiple of this
        skin_lines=1, omega_lines=1, box_wall_lines=1,
        omega_clearance=0.0,               # rod envelope -> clip inner face
        omega_neck_width=None,             # clip legs leave the skin at this width (None = rod_diameter)
        omega_foot_length=1.0,             # foot beyond the clip's outer face
        rod_min_gap=0.5,                   # rod surface to rod surface
        snap_to_previous=True,
        joint_mod_margin_pct=0.20,         # lap modifier: both rods at 1.2 x diameter + the gap
        box_le_pct=0.20, box_te_pct=0.30,  # webs at 20 % from LE and 30 % from TE
    ),
)
```

What changes against the default `"bore"` mode:

* **Rods run straight at a constant x/c, tangent to the skin.** The taper
  tilts them slightly, which is intended. They bear at
  `max(skin_wall, joint_thickness)` below the surface, so they also clear the
  joint sleeve.
* **Placement.** Span 0 is the master and is never moved (a collision raises).
  Each later rod is snapped to `rod_min_gap` beside the nearest rod of the
  previous span, so lapping rods share one clip. If that spot is taken the
  solver tries the other side, then the next inboard rod. After that it
  relaxes to the nearest free spot to the request, also keeping the clip off
  the webs. `print_layout` reports where every rod went.
* **Outputs:** `part` (body with omega pockets), `walls` (clips + webs),
  `le_cell_modifier` / `box_cell_modifier` / `te_cell_modifier`,
  `rod_joint_modifier` (capsules), `sleeve_modifier`. There is no bell modifier.

See `definitions/mk3/` for a worked build and how the walls reach the slicer.

## As a library

```python
from wing_assembler import compute_section_layout, build_all
from wing_assembler.generate import load_definition

wing = load_definition(Path("wing_definition.py"))
for sec in compute_section_layout(wing):
    geom = build_all(sec, wing)     # {'part', 'bell_modifier', ...}
```

## Airfoils

4-digit NACA is computed. Anything else is read from `airfoils/<name>.dat`
(Selig format), and fetched from airfoiltools.com into that directory on first
use.
