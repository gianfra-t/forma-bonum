from __future__ import annotations

import math

from build123d import Axis, Compound, Plane, Solid, Vector, VectorLike

from .channels import Channel


def skin_point(part: Solid, origin: VectorLike, direction: VectorLike, inset: float) -> Vector:
    o, d = Vector(origin), Vector(direction).normalized()
    hits = [(p, n) for p, n in part.find_intersection_points(Axis(o, d)) if (p - o).dot(d) > 1e-9]
    if not hits:
        raise ValueError(f"probe from {tuple(o)} along {tuple(d)} never leaves the part")
    p, n = min(hits, key=lambda h: (h[0] - o).dot(d))
    return p - d * (inset / abs(n.normalized().dot(d)))


def skin_clearance(part: Solid, channel: Channel, samples: int = 60) -> float:
    skin = Compound(part.faces())
    line = channel.centerline()
    walls = []
    for t in (i / samples for i in range(samples + 1)):
        p, tangent = line.position_at(t), line.tangent_at(t)
        if not part.is_inside(p):
            continue
        d, q, _ = skin.distance_to_with_closest_points(p)
        if abs((q - p).dot(tangent)) > 0.1 * d:
            d = Compound(part.intersect(Plane(origin=p, z_dir=tangent)).edges()).distance_to(p)
        walls.append(d)
    return min(walls, default=math.inf) - channel.profile.radius


def bend_radius(channel: Channel, samples: int = 200) -> float:
    line = channel.centerline()
    k = 0.0
    for t in (i / samples for i in range(samples + 1)):
        d1, d2 = line.derivative_at(t, 1), line.derivative_at(t, 2)
        k = max(k, d1.cross(d2).length / d1.length ** 3)
    return 1 / k if k else math.inf


def channel_gap(a: Channel, b: Channel) -> float:
    return a.centerline().distance_to(b.centerline()) - a.profile.radius - b.profile.radius
