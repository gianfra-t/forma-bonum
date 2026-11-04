import math
from pathlib import Path

from build123d import Ellipse, Location, Rectangle, extrude

from channel_cutter import Channel, channel_gap, cut_channels, export, hexagon, modifiers, skin_clearance

LINE = 0.38
LAYER = 0.12
SKIN = 2 * LINE - LAYER * (1 - math.pi / 4)

WIDTH = 15.0
FLAT = 0.2 * WIDTH
LENGTH = 290.0
AF = 2.4
PITCH = 6.0
EDGE = AF / 2 + SKIN

OUT = Path(__file__).resolve().parent / "output"


def height():
    return PITCH + 2 * EDGE


def bar(length=LENGTH):
    h = height()
    section = Rectangle(h, FLAT).moved(Location((h / 2, 0, 0)))
    for s in (-1, 1):
        section += Ellipse(h / 2, WIDTH / 2).moved(Location((h / 2, s * FLAT / 2, 0)))
    return extrude(section, length).solids()[0]


def centres():
    return [EDGE, EDGE + PITCH]


def build():
    rod, mod = hexagon(AF), hexagon(AF + 2 * (SKIN - 0.2))
    channels = [Channel(rod, [(x, 0, -1), (x, 0, LENGTH + 1)], mod, (0, 1, 0), f"rod_{i}")
                for i, x in enumerate(centres(), 1)]
    return bar(), channels


def report(part, channels, edge=EDGE):
    print(f"  section {height():.3f} x {WIDTH + FLAT} mm ({FLAT} flat), {LENGTH} long; skin {SKIN:.3f}, centre to wall {edge:.3f}")
    for c in channels:
        gaps = [channel_gap(c, d) for d in channels if d is not c]
        print(f"  {c.name:10s} x {c.points[0][0]:6.3f}  wall {skin_clearance(part, c):6.3f}  gap {min(gaps):6.3f}")


if __name__ == "__main__":
    part, channels = build()
    print(f"rod_test: {len(channels)} channels")
    report(part, channels)
    cut = cut_channels(part, channels)
    export(cut, OUT / "rod_test.step")
    export(cut, OUT / "rod_test.stl")
    export(modifiers(part, channels), OUT / "rod_test_modifier.stl")
    print(f"wrote {OUT}")
