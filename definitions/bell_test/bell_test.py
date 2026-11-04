import math
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from build123d import Compound, Solid, Vector, Wire
from shapely import affinity, segmentize
from shapely.geometry import Point, Polygon, box
from shapely.geometry.polygon import orient

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "rod_test"))
sys.path.insert(0, str(HERE.parent / "wire_test"))

from rod_test import FLAT, WIDTH, bar, height
from wire_test import LAYER, SKIN

from channel_cutter import export

LENGTH = 100.0
WIRES = (0.8, 1.0)
ARC_SEGMENTS = 24
FLANK_SEGMENTS = 24
MOUTH_SEGMENTS = 12
SAMPLES = 4000

OUT = HERE / "output"


@dataclass(frozen=True)
class Bell:
    name: str
    mouth: float
    crown: float = 1.15
    arc: float = 180.0
    smooth: bool = False

    def flank_k(self):
        r, phi = self.crown / 2, math.radians(self.arc) / 2
        u0, n0 = r * math.sin(phi), r + r * math.cos(phi)
        slope = math.tan(phi) * (self.mouth / 2 - u0) / n0
        assert slope > 1, f"{self.name}: mouth too narrow for a smooth flank"
        lo, hi = 1e-6, 50.0
        for _ in range(60):
            k = (lo + hi) / 2
            lo, hi = (k, hi) if k / (1 - math.exp(-k)) < slope else (lo, k)
        return k

    def outline(self):
        r, phi = self.crown / 2, math.radians(self.arc) / 2
        u0, n0 = r * math.sin(phi), r + r * math.cos(phi)
        ts = [i / FLANK_SEGMENTS for i in range(FLANK_SEGMENTS)]
        if self.smooth:
            k = self.flank_k()
            g = [(math.exp(-k * t) - math.exp(-k)) / (1 - math.exp(-k)) for t in ts]
        else:
            g = [1 - t for t in ts]
        flank = [(u0 + t * (self.mouth / 2 - u0), n0 * gi) for t, gi in zip(ts, g)]
        arc = [(r * math.sin(a), r + r * math.cos(a))
               for a in (phi - 2 * phi * i / ARC_SEGMENTS for i in range(ARC_SEGMENTS + 1))]
        mouth = [(-self.mouth / 2 + self.mouth * i / MOUTH_SEGMENTS, 0.0) for i in range(MOUTH_SEGMENTS + 1)]
        right = [(u, n) for u, n in reversed(flank)][:-1]
        left = [(-u, n) for u, n in flank][1:]
        return right + arc + left + mouth[:-1]

    def section(self):
        return Polygon(self.outline())


BELLS = (Bell("semi", 2.6), Bell("smooth", 3.0, arc=120.0, smooth=True),
         Bell("small", 2.0, crown=1.05, arc=120.0, smooth=True),
         Bell("mid", 4.5, crown=1.725, arc=120.0, smooth=True),
         Bell("large", 6.0, crown=2.3, arc=120.0, smooth=True))


def mod_section(bell):
    grown = bell.section().buffer(SKIN, quad_segs=4)
    return grown.intersection(box(-10, -(SKIN - 0.2), 10, 10))


def outer_section():
    h = height()
    s = box(0, -FLAT / 2, h, FLAT / 2)
    for y in (-FLAT / 2, FLAT / 2):
        s = s.union(affinity.scale(Point(h / 2, y).buffer(1, quad_segs=512), h / 2, WIDTH / 2))
    return s


class Contour:

    def __init__(self):
        inner = orient(outer_section().buffer(-SKIN, quad_segs=128), 1).exterior
        self.length = inner.length
        self.s = np.linspace(0, self.length, SAMPLES, endpoint=False)
        self.xy = np.array([inner.interpolate(d).coords[0] for d in self.s])
        t = np.roll(self.xy, -2, axis=0) - np.roll(self.xy, 2, axis=0)
        t /= np.linalg.norm(t, axis=1)[:, None]
        self.normal = np.stack([-t[:, 1], t[:, 0]], axis=1)

    def nearest(self, p):
        return float(self.s[np.argmin(np.linalg.norm(self.xy - p, axis=1))])

    def at(self, s, n):
        s = np.mod(s, self.length)
        x = np.interp(s, self.s, self.xy[:, 0], period=self.length)
        y = np.interp(s, self.s, self.xy[:, 1], period=self.length)
        nx = np.interp(s, self.s, self.normal[:, 0], period=self.length)
        ny = np.interp(s, self.s, self.normal[:, 1], period=self.length)
        k = np.hypot(nx, ny)
        return np.stack([x + n * nx / k, y + n * ny / k], axis=1)


def starts(contour):
    h = height()
    return [contour.nearest((SKIN, 0)), contour.nearest((h - SKIN, 0))]


def prism(contour, s0, outline):
    u, n = np.array(outline).T
    xy = contour.at(s0 + u, n)
    ends = [Wire.make_polygon([Vector(x, y, z) for x, y in xy], close=True) for z in (-1, LENGTH + 1)]
    return Solid.make_loft(ends, ruled=True)


def build(bell):
    contour = Contour()
    mod = list(segmentize(mod_section(bell), 0.1).exterior.coords[:-1])
    channels = [prism(contour, s, bell.outline()) for s in starts(contour)]
    mods = [prism(contour, s, mod) for s in starts(contour)]
    return bar(LENGTH), channels, mods


def plot(bell, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Circle


    fig, ax = plt.subplots(figsize=(7, 4.2))
    ax.axhspan(-SKIN, 0, color="0.85", label=f"skin {SKIN:.3f}")
    ax.fill(*mod_section(bell).exterior.xy, color="tab:orange", alpha=0.15, label="100 % infill modifier")
    ax.fill(*bell.section().exterior.xy, color="tab:blue", alpha=0.35, label="channel (epoxy)")
    ax.add_patch(Circle((0, WIRES[0] / 2), WIRES[0] / 2, color="0.2", label=f"{WIRES[0]} wire, on the skin"))
    ax.add_patch(Circle((0, bell.crown / 2), bell.crown / 2, fill=False, ls="--", color="0.4",
                        label=f"crown {bell.crown}, {bell.arc:.0f} deg"))
    ax.annotate("", (-bell.mouth / 2, 0.05), (bell.mouth / 2, 0.05), arrowprops=dict(arrowstyle="<->"))
    ax.text(bell.mouth / 2 - 0.9, 0.12, f"mouth {bell.mouth}", fontsize=8)
    for s in (-1, 1):
        ax.axvline(s * FLAT / 2, color="0.5", lw=0.6, ls=":", label="end of the flat wall" if s > 0 else None)
    ax.set_aspect("equal")
    ax.set_xlabel("mm along the wall")
    ax.set_ylabel("mm inwards from the skin's inner face")
    ax.set_title(f"bell {bell.name}: {bell.section().area:.3f} mm2", loc="left", fontsize=10)
    ax.legend(fontsize=7, loc="center left", bbox_to_anchor=(1, 0.5))
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def epoxy_report(bell, length=LENGTH):
    for w in WIRES:
        epoxy = bell.section().area - math.pi * w ** 2 / 4
        print(f"  {w} wire: epoxy {epoxy:.3f} mm2 -> {epoxy * length / 1000:.3f} ml per channel")


if __name__ == "__main__":
    print(f"section {height():.3f} x {WIDTH + FLAT} mm, {LENGTH} long; layer {LAYER}, skin {SKIN:.3f}")
    for bell in BELLS:
        name = f"bell_{bell.name}_{bell.crown:.2f}"
        print(f"{name}: mouth {bell.mouth}, crown {bell.crown} over {bell.arc:.0f} deg, "
              f"{'smooth' if bell.smooth else 'straight'} flanks, area {bell.section().area:.3f} mm2")
        epoxy_report(bell)
        part, channels, mods = build(bell)
        cut = part.cut(*channels)
        print(f"  channels {(part.volume - cut.volume) / 2:.1f} mm3 each")
        export(cut, OUT / f"{name}.step")
        export(cut, OUT / f"{name}.stl")
        export(Compound(children=[s for m in mods for s in m.intersect(part).solids()]), OUT / f"{name}_modifier.stl")
        plot(bell, OUT / f"{name}_section.png")
    print(f"wrote {OUT}")
