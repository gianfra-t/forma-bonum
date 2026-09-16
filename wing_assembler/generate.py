"""Build a wing panel from ANY definition module, into ANY output directory.

A definition is a .py exposing a module-level `wing = WingDefinition(...)`.
The STLs land next to it by default, so a variant under `definitions/<name>/`
builds into `definitions/<name>/output/`.

    wing-assembler definitions/mk2/wing_definition_mk2.py
    wing-assembler <def.py> --out <dir> --sections 0,1

Equivalently: python3 -m wing_assembler.generate <def.py>

Emits per print section:
    section_NN_part.stl
    section_NN_bell_modifier.stl
    section_NN_rod_joint_modifier.stl
    section_NN_sleeve_modifier.stl   (female sections only)
    section_NN_topopt_modifier.stl

The modifier STLs are PrusaSlicer MODIFIER VOLUMES, not parts -- they raise
the infill locally around the bores, across each rod-to-rod lap, and in the sleeve
zone.  Load them as modifiers on the corresponding part, do not print them.

A definition with construction="omega" emits instead:
    section_NN_part.stl
    section_NN_walls.stl                 omega clips + box webs (see README)
    section_NN_le_cell_modifier.stl
    section_NN_box_cell_modifier.stl
    section_NN_te_cell_modifier.stl
    section_NN_rod_joint_modifier.stl
    section_NN_sleeve_modifier.stl       (female sections only)
"""
from __future__ import annotations

import argparse
import importlib.util
import sys
import time
import traceback
from pathlib import Path

import build123d as b123

from .section_layout import compute_section_layout, print_layout, chord_at
from .wing_builder import build_all


SKIP_MSG = {
    "bell_modifier": "no rods, skipped",
    "rod_joint_modifier": "no rod joint, skipped",
    "sleeve_modifier": "not a female section, skipped",
    "topopt_modifier": "no topopt patch, skipped",
}


def load_definition(path: Path):
    """Import a definition module by file path and return its `wing`."""
    path = path.resolve()
    # A definition imports WingDefinition/RodSection from the installed package;
    # its own directory goes on sys.path so it can also import siblings.
    sys.path.insert(0, str(path.parent))
    spec = importlib.util.spec_from_file_location(path.stem, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    if not hasattr(mod, "wing"):
        raise SystemExit(f"{path} defines no `wing`")
    return mod.wing


def export_stl(shape, path: Path) -> bool:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        b123.export_stl(shape, str(path))
        print(f"  ok  {path.name}  ({path.stat().st_size/1024:.1f} KB)")
        return True
    except Exception as e:  # noqa: BLE001
        print(f"  FAIL {path.name}: {e}", file=sys.stderr)
        return False


def run(def_path: Path, out_dir: Path, only: set[int] | None) -> int:
    wing = load_definition(def_path)
    print(f"Definition: {def_path}")
    print("Computing section layout...")
    sections = compute_section_layout(wing)
    print_layout(wing, sections)

    out_dir.mkdir(parents=True, exist_ok=True)
    ok = fail = 0
    t0 = time.time()

    for sec in sections:
        if only is not None and sec.index not in only:
            continue
        prefix = f"section_{sec.index:02d}"
        print(f"\n-- {prefix}  z={sec.z_start:.0f}->{sec.z_end:.0f}mm  "
              f"chord={chord_at(sec.z_start, wing):.1f}->{chord_at(sec.z_end, wing):.1f}mm  "
              f"holes={len(sec.holes)} --")
        try:
            geom = build_all(sec, wing)
        except Exception:  # noqa: BLE001
            print("  FAIL build_all:")
            traceback.print_exc()
            fail += 1
            continue

        for key, shape in geom.items():
            if shape is None:
                print(f"  --  {prefix}_{key}.stl  ({SKIP_MSG.get(key, 'empty, skipped')})")
                continue
            good = export_stl(shape, out_dir / f"{prefix}_{key}.stl")
            ok += good
            fail += (not good)

    print(f"\n{'='*62}")
    print(f"Done in {time.time()-t0:.1f}s -- {ok} STLs written, {fail} failed")
    print(f"Output: {out_dir}")
    print(f"{'='*62}")
    return 1 if fail else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("definition", type=Path, help="path to a wing definition .py")
    ap.add_argument("--out", type=Path, default=None,
                    help="output dir (default: <definition dir>/output)")
    ap.add_argument("--sections", default=None,
                    help="comma-separated section indices to build (default: all)")
    a = ap.parse_args()
    out = a.out or a.definition.resolve().parent / "output"
    only = {int(s) for s in a.sections.split(",")} if a.sections else None
    return run(a.definition, out, only)


if __name__ == "__main__":
    sys.exit(main())
