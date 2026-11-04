# channel_cutter

Reinforcement channels for any solid: a cross-section swept along a smooth
centerline, cut from the part. A second cross-section swept along the same line
is the slicer modifier volume.

## Use

```python
from channel_cutter import (
    Channel, circle, hexagon, load_solid, skin_point, skin_clearance, cut_channels, modifiers, export,
)

part = load_solid("part.step")           # or .stl

# Centerline points: here, each 1.77 mm under the skin (hexagon radius 1.27 + 0.5 margin),
# probing from a point inside the part towards the skin.
pts = [skin_point(part, origin, direction, inset=1.77) for origin, direction in probes]

ch = Channel(hexagon(2.2), pts, modifier=circle(5.0), x_dir=(0, 1, 0))
print(skin_clearance(part, ch))          # thinnest wall between channel and skin

export(cut_channels(part, [ch]), "part_cut.stl")
export(modifiers(part, [ch]), "part_modifier.stl")
```

| piece | what |
|---|---|
| `circle(d)`, `hexagon(across_flats)`, `regular_polygon(n, across_flats)`, `polygon(pts)` | cross-sections; `.radius` is the farthest point from the centre, used for clearances |
| `Channel(profile, points, modifier, x_dir, ruled)` | centerline through `points` (a line for 2, else a spline); `x_dir` sets the profile's local x, fixed or a function of position; `ruled` joins the sections flat (exact, more faces: the smooth loft can bulge near its ends) |
| `skin_point(part, origin, direction, inset)` | where a probe leaves the skin, moved back `inset` normal to the skin |
| `skin_clearance(part, channel)` | thinnest wall to the skin, measured in the plane normal to the centerline |
| `channel_gap(a, b)` | wall between two channels (centerline distance minus both radii) |
| `bend_radius(channel)` | tightest bend of the centerline, for stiff rods |
| `cut_channels`, `modifiers` | the cut part; each modifier sweep clipped to the part |
| `load_solid`, `export` | STEP / STL in, STEP / STL out (STL meshed at 0.02 mm absolute) |

The channel solid is a loft of the profile placed normal to the centerline every
`section_step` mm; in each section the profile x is `x_dir` projected onto it
(fixed, or `x_dir(centre)` to follow a twist). Channels are assumed not to intersect;
`channel_gap` checks it, `bend_radius` gives the tightest bend for stiff rods.

## Sleeve joints

The last step: split the finished part on planes into pieces that print, joined
male into female as in wing_assembler.

```python
from channel_cutter import Cut, SleeveJoint, cut_joints, export, load_solid

joint = SleeveJoint(walls=2)                     # 2 x 0.45 mm sleeve; the rest as wing_assembler
pieces = cut_joints(load_solid("part.step"), [
    Cut(origin=(175, 0, 50), normal=(1, 0, 0), joint=joint, male="front", female="rear"),
])
for p in pieces:
    export(p.solid, f"{p.name}.step")
    for kind, mods in p.modifiers.items():      # 'peg' / 'sleeve'
        ...
```

The plane through `origin` is the seam on the skin; `normal` points from the male
into the female, and `origin` must lie inside the section to cut (the plane may
cross other parts of the solid, which are left alone). Cuts apply in order, each
to whichever piece holds its section.

Past the seam the female keeps its outer skin as a sleeve `walls x line_width`
thick and is hollowed down to a floor `length` in; the male grows a peg into that
hollow, `clearance + epoxy_gap` inside the sleeve and `axial_gap` short of the
floor. Both are prisms along the normal, so the peg slides straight in. Their
outline is the part's section at every station through the joint, intersected:
where the part tapers or sweeps the sleeve gets thicker and the peg smaller.
Channels and hollow cores pass through the peg unchanged.

| `SleeveJoint` | default | |
|---|---|---|
| `length` | 15.0 | seam to sleeve floor |
| `walls`, `line_width` | 1, 0.45 | sleeve thickness |
| `clearance`, `epoxy_gap` | 0.0, 0.3 | radial gap, peg to sleeve |
| `axial_gap` | 0.3 | peg end to floor |
| `floor_layers`, `layer_height` | 4, 0.2 | the sleeve modifier reaches this past the floor |
| `modifier_length` | 0.0 | both modifiers reach this much further into their part |

Modifiers passed to `cut_joints(..., modifiers={"channel": [...]})` are clipped
onto the pieces. Its own: `sleeve` covers the female's sleeve and floor (set its wall count and
solid floor layers there), `peg` covers the male's peg (its walls and end layers).

Work in STEP and mesh at the end, from the written STEP: meshing a boolean result
directly can take a loose edge tolerance from OCC as licence to facet the skin.

## Demo

`definitions/apc_20x12/` builds an APC 20x12 blade and hub (`prop.py`) and
reinforces them two ways: `rods_2mm.py` (six 2 mm rods) and `fibers_08mm.py`
(18 bendable 0.8 mm fibres, around the perimeter, one to the tip).
`definitions/apc_10x7/triangle_08mm.py` puts two 0.8 mm fibres in an APC 10x7
through triangular channels that turn with the twist, fitted with their true
shape rather than their circumscribed circle.

```bash
pip install -e .
python definitions/apc_20x12/fibers_08mm.py     # -> definitions/apc_20x12/output/fibers_08mm/
```

The TL-1 master (moved to ConAero `analysis/tl-1/tl1_tandem/fabrication/airframe/`,
its own uv environment with this repo installed editable) is the fused tandem (600 mm pod)
cut first for a service door seated in a rabbet across the pod's top, given
an 8 mm hinge bore 70 mm into each tip and a cable tunnel from bore to bore
that opens into the pod's hollow, then cut into ten print pieces: the door,
the pod in three, both front wings at |y| 55 and the rear wing panels in two
each. Its layouts add the channels: `pod/` 2 mm carbon rods, `pod_wire/`
0.8 mm wires, both with the elevons' pull-pull lines. See its README.

```bash
cd ~/root/ConAero/analysis/tl-1/tl1_tandem/fabrication/airframe
uv run python pod_wire/pod_wire.py --stl     # -> pod_wire/output/
```
