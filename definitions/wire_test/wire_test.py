import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "rod_test"))

from rod_test import FLAT, LENGTH, LINE, WIDTH, bar, height

from channel_cutter import (Channel, channel_gap, circle, cut_channels, export, modifiers,
                            regular_polygon, skin_clearance)

LAYER = 0.2
SKIN = 2 * LINE - LAYER * (1 - math.pi / 4)
SIZES = (1.0, 1.05, 1.1, 1.15, 1.2, 1.25)

OUT = HERE / "output"


def edge(inscribed):
    return inscribed / 2 + SKIN


def build(inscribed):
    e = edge(inscribed)
    wire, mod = regular_polygon(3, inscribed), circle(2 * (e - 0.2))
    xs = (e, height() - e)
    channels = [Channel(wire, [(x, 0, -1), (x, 0, LENGTH + 1)], mod, (side, 0, 0), f"wire_{i}")
                for i, (x, side) in enumerate(zip(xs, (1, -1)), 1)]
    return bar(), channels


def report(part, channels):
    print(f"  section {height():.3f} x {WIDTH + FLAT} mm ({FLAT} flat), {LENGTH} long; layer {LAYER}, skin {SKIN:.3f}")
    for c in channels:
        gaps = [channel_gap(c, d) for d in channels if d is not c]
        print(f"  {c.name:10s} x {c.points[0][0]:6.3f}  wall {skin_clearance(part, c):6.3f}  gap {min(gaps):6.3f}")


if __name__ == "__main__":
    for size in SIZES:
        part, channels = build(size)
        name = f"wire_test_{size:.2f}"
        print(f"{name}: inscribed {size}, centre to wall {edge(size):.3f}")
        report(part, channels)
        cut = cut_channels(part, channels)
        export(cut, OUT / f"{name}.step")
        export(cut, OUT / f"{name}.stl")
        export(modifiers(part, channels), OUT / f"{name}_modifier.stl")
    print(f"wrote {OUT}")
