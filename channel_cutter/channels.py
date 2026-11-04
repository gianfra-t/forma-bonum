from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass

from build123d import Compound, Edge, Plane, Solid, Vector, VectorLike, Wire


@dataclass(frozen=True)
class Profile:
    radius: float
    points: tuple = ()

    def wire(self, plane: Plane) -> Wire:
        if not self.points:
            return Wire.make_circle(self.radius, plane)
        return Wire.make_polygon([plane.from_local_coords(p) for p in self.points], close=True)


def circle(diameter: float) -> Profile:
    return Profile(diameter / 2)


def polygon(points) -> Profile:
    pts = tuple((float(x), float(y)) for x, y in points)
    return Profile(max(math.hypot(*p) for p in pts), pts)


def regular_polygon(sides: int, across_flats: float) -> Profile:
    r = across_flats / 2 / math.cos(math.pi / sides)
    return polygon([(r * math.cos(2 * math.pi * k / sides), r * math.sin(2 * math.pi * k / sides))
                    for k in range(sides)])


def hexagon(across_flats: float) -> Profile:
    return regular_polygon(6, across_flats)


@dataclass
class Channel:
    profile: Profile
    points: list
    modifier: Profile | None = None
    x_dir: VectorLike | Callable[[Vector], VectorLike] | None = None
    name: str = ""
    section_step: float = 4.0
    start_dir: VectorLike | None = None
    ruled: bool = False

    def centerline(self) -> Edge:
        pts = [Vector(p) for p in self.points]
        if len(pts) == 2:
            return Edge.make_line(*pts)
        if self.start_dir is None:
            return Edge.make_spline(pts)
        return Edge.make_spline(pts, tangents=[Vector(self.start_dir), pts[-1] - pts[-2]])

    def solid(self, profile: Profile | None = None) -> Solid:
        path = self.centerline()
        x_ref = _any_normal(path.tangent_at(0)) if self.x_dir is None else self.x_dir
        n = max(2, round(path.length / self.section_step) + 1)
        sections = []
        for t in (i / (n - 1) for i in range(n)):
            o, z = path.position_at(t), path.tangent_at(t)
            x_dir = Vector(x_ref(o) if callable(x_ref) else x_ref)
            x = (x_dir - z * x_dir.dot(z)).normalized()
            sections.append((profile or self.profile).wire(Plane(origin=o, x_dir=x, z_dir=z)))
        return Solid.make_loft(sections, ruled=self.ruled)

    def modifier_solid(self) -> Solid:
        return self.solid(self.modifier)


def _any_normal(v: Vector) -> Vector:
    return v.cross(Vector(1, 0, 0) if abs(v.X) < 0.9 else Vector(0, 1, 0))


def cut_channels(part: Solid, channels: list[Channel]) -> Solid:
    return part.cut(*[c.solid() for c in channels])


def modifiers(part: Solid, channels: list[Channel]) -> Compound | None:
    clipped = [c.modifier_solid().intersect(part) for c in channels if c.modifier]
    mods = [s for m in clipped if m is not None for s in m.solids()]
    return Compound(children=mods) if mods else None
