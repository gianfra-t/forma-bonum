"""Bolt a rectangular test plate onto the root of mk2 section 00.

Load-test fixture only -- this is NOT part of the flying wing, so it lives
outside `wing_definition_mk2.py` and writes its own STL rather than touching
`section_00_part.stl`.

The plate is a plain rectangular block sitting BELOW the root face (local
z < 0, the section itself runs z = 0 -> 200), sized from the root chord:

    length (x)  root chord + 20 mm  = 220 mm   (~10 mm proud of LE and TE)
    width  (y)  75 mm                          (section is 25.6 mm deep)
    height (z)  20 mm                          (grip length for the rig)

and centred on the root section's own bounding box, so the border is even all
the way round.

All ten primary rod bores of section 00 run parallel to z at a fixed (x, y), so
they extend into the plate as straight cylinders.  They are cut clear THROUGH
the base face: the rods seat the full 20 mm of the plate and the test load
goes into the rods, not into the printed skin.

    python3 definitions/mk2/add_root_plate.py [--out <file.stl>]
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import build123d as b123
from build123d import Plane, Solid

HERE = Path(__file__).resolve().parent
WA = HERE.parent.parent                      # structures/wing-assembler
sys.path.insert(0, str(WA))

from wing_assembler.generate import load_definition   # noqa: E402
from wing_assembler.naca import naca4_polygon_pts               # noqa: E402
from wing_assembler.section_layout import compute_section_layout, chord_at  # noqa: E402
from wing_assembler.wing_builder import build_all               # noqa: E402

DEFINITION = HERE / "wing_definition_mk2.py"
DEFAULT_OUT = HERE / "output" / "section_00_part_with_root_plate.stl"

PLATE_LENGTH_MARGIN = 20.0    # plate is this much longer than the root chord
PLATE_WIDTH = 75.0
PLATE_HEIGHT = 20.0
BORE_OVERSHOOT = 1.0          # bore runs this far past both plate faces


def build(out_path: Path) -> None:
    wing = load_definition(DEFINITION)
    sec = compute_section_layout(wing)[0]
    c_root = chord_at(sec.z_start, wing)

    print(f"section 00: z {sec.z_start:.0f}->{sec.z_end:.0f} mm, "
          f"chord {c_root:.1f} mm, {len(sec.holes)} hole pairs")

    # ── plate footprint: centred on the root profile's bounding box ──
    prof = naca4_polygon_pts(wing.naca, c_root, 60)
    xs = [p[0] for p in prof]
    ys = [p[1] for p in prof]
    x_mid = (min(xs) + max(xs)) / 2
    y_mid = (min(ys) + max(ys)) / 2

    length = c_root + PLATE_LENGTH_MARGIN
    x0 = x_mid - length / 2
    y0 = y_mid - PLATE_WIDTH / 2
    z0 = -PLATE_HEIGHT                       # base of the plate
    print(f"plate:      {length:.0f} x {PLATE_WIDTH:.0f} x {PLATE_HEIGHT:.0f} mm  "
          f"x[{x0:.1f},{x0+length:.1f}] y[{y0:.1f},{y0+PLATE_WIDTH:.1f}] z[{z0:.1f},0.0]")

    plate = Solid.make_box(length, PLATE_WIDTH, PLATE_HEIGHT,
                           Plane(origin=(x0, y0, z0)))

    # ── wing section, bores already subtracted ──
    part = build_all(sec, wing)["part"]

    solid = part.fuse(plate)

    # ── carry every root bore down through the plate ──
    # Primary rods only: the non-primary holes belong to the next span's rods and
    # start 175 mm out, nowhere near the root face.
    r = wing.rod_diameter / 2
    h = PLATE_HEIGHT + 2 * BORE_OVERSHOOT
    n_bores = 0
    for hole in sec.holes:
        if not hole.is_primary or hole.z0 > 1e-6:
            continue
        for y in (hole.yu0, hole.yl0):
            cyl = Solid.make_cylinder(
                r, h, Plane(origin=(hole.x0, y, z0 - BORE_OVERSHOOT)))
            solid = solid - cyl
            n_bores += 1
    print(f"bores:      {n_bores} x d{wing.rod_diameter:.1f} mm, "
          f"cut through the base face")

    bb = solid.bounding_box()
    print(f"result:     bbox x[{bb.min.X:.1f},{bb.max.X:.1f}] "
          f"y[{bb.min.Y:.1f},{bb.max.Y:.1f}] z[{bb.min.Z:.1f},{bb.max.Z:.1f}]  "
          f"volume {solid.volume/1000:.1f} cm3")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    b123.export_stl(solid, str(out_path))
    print(f"wrote       {out_path}  ({out_path.stat().st_size/1024:.0f} KB)")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args()
    t = time.time()
    build(args.out)
    print(f"done in {time.time()-t:.1f}s")


if __name__ == "__main__":
    main()
