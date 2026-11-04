from __future__ import annotations

import math
import warnings
from dataclasses import dataclass, field

from build123d import Compound, Face, Keep, Plane, Shape, Solid, Vector, VectorLike, Wire
from OCP.BRepAdaptor import BRepAdaptor_CompCurve
from OCP.GCPnts import GCPnts_QuasiUniformAbscissa
from shapely.geometry import MultiPolygon, Point, Polygon, box
from shapely.ops import unary_union

OVERLAP = 0.05
SAMPLE = 0.25
SIMPLIFY = 0.005


@dataclass(frozen=True)
class SleeveJoint:
    length: float = 15.0
    walls: int = 1
    line_width: float = 0.45
    floor_layers: int = 4
    layer_height: float = 0.2
    clearance: float = 0.0
    epoxy_gap: float = 0.3
    axial_gap: float = 0.3
    modifier_length: float = 0.0
    station_step: float = 1.0

    @property
    def sleeve(self) -> float:
        return self.walls * self.line_width

    @property
    def gap(self) -> float:
        return self.clearance + self.epoxy_gap

    @property
    def floor(self) -> float:
        return self.floor_layers * self.layer_height


@dataclass
class Cut:
    origin: VectorLike
    normal: VectorLike
    joint: SleeveJoint = field(default_factory=SleeveJoint)
    male: str | None = None
    female: str | None = None


@dataclass
class Piece:
    name: str
    solid: Solid
    modifiers: dict[str, list[Solid]] = field(default_factory=dict)


def cut_joints(part: Solid, cuts: list[Cut], name: str = "part",
               modifiers: dict[str, list[Solid]] | None = None) -> list[Piece]:
    pieces = [Piece(name, part)]
    for k, cut in enumerate(cuts):
        plane = Plane(origin=cut.origin, z_dir=cut.normal)
        found = [(i, poly, polys) for i, p in enumerate(pieces)
                 for polys in [_islands(p.solid, plane)] for poly in polys if poly.contains(Point(0, 0))]
        if not found:
            raise ValueError(f"cut {k}: origin {tuple(Vector(cut.origin))} is inside no section of any piece")
        i, island, others = found[0]
        pieces[i:i + 1] = _split(pieces[i], plane, island, [o for o in others if o is not island], cut)
    for kind, mods in (modifiers or {}).items():
        for p in pieces:
            box = p.solid.bounding_box()
            p.modifiers.setdefault(kind, []).extend(
                s for m in mods if box.intersects(m.bounding_box()) for s in _solids(m.intersect(p.solid)))
    return pieces


def _split(piece: Piece, plane: Plane, island: Polygon, others: list[Polygon], cut: Cut) -> list[Piece]:
    j = cut.joint
    solid = piece.solid

    polys = [island]
    n = max(2, math.ceil(j.length / j.station_step))
    window = island.buffer(max(50.0, 5 * j.length)).bounds
    for s in (j.length * k / n for k in range(1, n + 1)):
        prev = polys[-1]
        best = max(_islands(solid, plane.offset(s), window), key=lambda p: p.intersection(prev).area, default=None)
        if best is None or best.intersection(prev).area == 0:
            raise ValueError(f"{piece.name}: the part ends {s:.1f} mm past the seam, inside the joint")
        polys.append(best)
    outline = polys[0]
    for p in polys[1:]:
        outline = outline.intersection(p)
    cavity = _inset(outline, j.sleeve, piece.name)
    peg = _inset(outline, j.sleeve + j.gap, piece.name)

    margin = min([1.0] + [island.distance(o) / 2 for o in others])
    if margin <= 0:
        raise ValueError(f"{piece.name}: the section at the seam touches another one in the same plane")
    sides = _solids(solid.split(_face(plane, island.buffer(margin), 0.0), keep=Keep.ALL))
    o, nz = plane.origin, plane.z_dir

    def beyond(s: Solid) -> bool:
        return all((Vector(v) - o).dot(nz) > -1e-4 for v in s.vertices()) and (s.center() - o).dot(nz) > 0

    female = [s for s in sides if beyond(s)]
    male = [s for s in sides if not beyond(s)]
    if len(female) != 1 or len(male) != 1:
        raise ValueError(f"{piece.name}: the seam split it into {len(male)} male / {len(female)} female solids")

    female = _one(female[0].cut(_prism(plane, cavity, -OVERLAP, j.length)), f"{piece.name} female")
    peg_solid = solid.intersect(_prism(plane, peg, -OVERLAP, j.length - j.axial_gap))
    male = _one(male[0].fuse(*_solids(peg_solid)), f"{piece.name} male")

    foot = unary_union(polys).buffer(1.0)
    m = Piece(cut.male or piece.name, male)
    f = Piece(cut.female or piece.name, female)
    for kind, mods in piece.modifiers.items():
        for mod in mods:
            for side in (m, f):
                side.modifiers.setdefault(kind, []).extend(_solids(mod.intersect(side.solid)))
    m.modifiers.setdefault("peg", []).extend(_solids(
        _prism(plane, foot, -j.modifier_length, j.length - j.axial_gap).intersect(male)))
    f.modifiers.setdefault("sleeve", []).extend(_solids(
        _prism(plane, foot, 0.0, j.length + j.floor + j.modifier_length).intersect(female)))
    return [m, f]


def _islands(solid: Solid, plane: Plane, window: tuple | None = None) -> list[Polygon]:
    if window is None:
        size = 2 * solid.bounding_box().diagonal
        window = (-size, -size, size, size)
    sec = solid.intersect(_face(plane, box(*window), 0.0))
    polys = []
    for f in (sec.faces() if sec is not None else []):
        w = f.outer_wire()
        curve = BRepAdaptor_CompCurve(w.wrapped)
        a = GCPnts_QuasiUniformAbscissa(curve, max(64, math.ceil(w.length / SAMPLE)))
        pts = [plane.to_local_coords(Vector(curve.Value(a.Parameter(i)))) for i in range(1, a.NbPoints() + 1)]
        poly = Polygon([(p.X, p.Y) for p in pts]).buffer(0)
        polys.extend(poly.geoms if isinstance(poly, MultiPolygon) else [poly])
    return polys


def _inset(outline: Polygon, d: float, name: str) -> Polygon:
    core = outline.buffer(-d)
    if core.is_empty:
        raise ValueError(f"{name}: the section is thinner than {2 * d:.2f} mm through the joint, no room for a peg")
    if isinstance(core, MultiPolygon):
        parts = sorted(core.geoms, key=lambda g: g.area, reverse=True)
        warnings.warn(f"{name}: the peg outline breaks in {len(parts)}; keeping the largest, "
                      f"{sum(g.area for g in parts[1:]):.1f} mm^2 dropped")
        core = parts[0]
    return core


def _face(plane: Plane, poly: Polygon, z: float) -> Face:
    pts = poly.simplify(SIMPLIFY).exterior.coords[:-1]
    return Face(Wire.make_polygon([plane.from_local_coords((x, y, z)) for x, y in pts], close=True))


def _prism(plane: Plane, poly: Polygon, z0: float, z1: float) -> Solid:
    return Solid.extrude(_face(plane, poly, z0), plane.z_dir * (z1 - z0))


def _solids(shape) -> list[Solid]:
    if shape is None:
        return []
    if isinstance(shape, Shape):
        return list(shape.solids())
    return [s for sh in shape for s in _solids(sh)]


def _one(shape, what: str) -> Solid:
    solids = _solids(shape)
    if len(solids) != 1:
        raise ValueError(f"{what}: expected one solid, got {len(solids)}")
    return solids[0]


def compound(solids: list[Solid]) -> Compound | None:
    return Compound(children=solids) if solids else None
