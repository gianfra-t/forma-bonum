"""build123d wire and solid helpers: point lists in, Wires/Solids/Compounds out."""
from build123d import Vector, Wire, Solid, Compound, Plane

from ..naca import naca4_polygon_pts, offset_polygon


def make_wire(pts_2d: list, z: float) -> Wire:
    """Build a closed Wire from 2D [x,y] points at a given Z height."""
    vecs = [Vector(float(p[0]), float(p[1]), z) for p in pts_2d]
    vecs.append(vecs[0])  # close
    return Wire.make_polygon(vecs)


def make_wire3d(pts_3d: list) -> Wire:
    """Build a closed Wire from pre-computed 3D [x,y,z] points."""
    vecs = [Vector(float(p[0]), float(p[1]), float(p[2])) for p in pts_3d]
    vecs.append(vecs[0])  # close
    return Wire.make_polygon(vecs)


def naca_wire(naca: str, chord: float, z: float, n: int = 60) -> Wire:
    pts = naca4_polygon_pts(naca, chord, n)
    return make_wire(pts, z)


def naca_wire_offset(naca: str, chord: float, z: float,
                     inward: float, n: int = 60) -> Wire:
    """NACA wire shrunk inward by `inward` mm (positive = shrink)."""
    pts = naca4_polygon_pts(naca, chord, n)
    pts_off = offset_polygon(pts, inward)
    return make_wire(pts_off, z)


def loft_solid(wires: list) -> Solid:
    """Loft a solid through a list of Wires. Unwraps ShapeList if needed."""
    result = Solid.make_loft(wires)
    # build123d may return a ShapeList when loft produces compound shapes
    if hasattr(result, '__iter__') and not isinstance(result, Solid):
        shapes = list(result)
        if not shapes:
            raise ValueError("make_loft returned empty ShapeList")
        result = shapes[0]
        for s in shapes[1:]:
            result = result.fuse(s)
    return result


def rod_cylinder(x0, y0, x1, y1, z0, z1, r):
    """
    Tapered rod hole from (x0,y0,z0) to (x1,y1,z1) with radius r.
    Approximated as loft of two circles.
    """
    # Circle at bottom
    c0 = Wire.make_circle(r, Plane(origin=(x0, y0, z0), z_dir=(0, 0, 1)))
    # Circle at top
    c1 = Wire.make_circle(r, Plane(origin=(x1, y1, z1), z_dir=(0, 0, 1)))
    return loft_solid([c0, c1])


def compound_list(solids: list):
    """Build a Compound from a list of solids. Returns None if empty."""
    if not solids:
        return None
    return Compound(children=solids)


def fuse_all(solids: list):
    """One shape from many; disjoint pieces come back from fuse as a list."""
    if not solids:
        return None
    fused = solids[0] if len(solids) == 1 else solids[0].fuse(*solids[1:])
    return fused if isinstance(fused, (Solid, Compound)) else Compound(children=list(fused))
