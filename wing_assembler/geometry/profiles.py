"""2D profile point generators and their placement on the airfoil surface.

Pure math: returns lists of [x, y] points, no build123d.
"""
import math

from ..naca import naca4_y_at


def bell_pts(bw, bh, bshape, n=20) -> list:
    """2D bell profile points (local: small end at 0, opens upward toward skin)."""
    pts = []
    for i in range(n + 1):
        x = -bw / 2 + bw * i / n
        y = bh * (abs(2 * x / bw) ** bshape)
        pts.append([x, y])
    pts.append([bw / 2, bh])
    pts.append([-bw / 2, bh])
    return pts


def ellipse_pts(xa, ya, xb, yb, thickness, n=48) -> list:
    """Ellipse wrapping the segment between two rod centres.

    Major axis lies along A->B with semi-axis |AB|/2 + thickness/2, minor axis is
    thickness/2, so the shape is a capsule-like ellipse of constant `thickness`
    across the load path and closing off just beyond each rod.
    """
    cx, cy = (xa + xb) / 2, (ya + yb) / 2
    dx, dy = xb - xa, yb - ya
    length = math.hypot(dx, dy)
    if length < 1e-9:
        ux, uy = 1.0, 0.0
    else:
        ux, uy = dx / length, dy / length
    vx, vy = -uy, ux                       # minor axis direction

    a = length / 2 + thickness / 2
    b = thickness / 2
    pts = []
    for i in range(n):
        t = 2 * math.pi * i / n
        e1 = a * math.cos(t)
        e2 = b * math.sin(t)
        pts.append([cx + e1 * ux + e2 * vx, cy + e1 * uy + e2 * vy])
    return pts


def capsule_pts(xa, ya, xb, yb, radius, n=16) -> list:
    """Stadium around segment A-B: both rods at `radius` and everything between."""
    dx, dy = xb - xa, yb - ya
    length = math.hypot(dx, dy)
    ux, uy = (dx / length, dy / length) if length > 1e-9 else (1.0, 0.0)
    base = math.atan2(uy, ux)
    pts = []
    for (cx, cy), a0 in (((xb, yb), base - math.pi / 2), ((xa, ya), base + math.pi / 2)):
        for i in range(n + 1):
            a = a0 + math.pi * i / n
            pts.append([cx + radius * math.cos(a), cy + radius * math.sin(a)])
    return pts


def place_at_normal(x_rod: float, y_rod: float,
                    chord: float, naca: str, sign_y: float,
                    z: float, offset_dist: float,
                    local_pts: list, flip_y: bool = False) -> list:
    """
    Transform local bell/ellipse pts so they sit tangent to the profile surface
    at (x_rod, y_rod), normal to the surface.
    local_pts open upward (+Y). We map +Y to the outward normal.
    Returns 2D [x, y] points; the caller adds z.
    """
    x_frac = x_rod / chord + 0.5
    # Approximate surface normal using finite difference on NACA y
    dx = 0.002
    y1 = naca4_y_at(naca, max(0.01, x_frac - dx)) * chord
    y2 = naca4_y_at(naca, min(0.99, x_frac + dx)) * chord

    # Tangent vector (pointing rightward along chord)
    tx = 2 * dx * chord
    ty = y2 - y1
    length = math.sqrt(tx ** 2 + ty ** 2)

    # Outward normal (+Y points outward)
    if sign_y > 0:
        nx = -ty / length
        ny =  tx / length
    else:
        # Lower surface tangent is (tx, -ty). Outward normal (ny < 0) is (-ty, -tx).
        nx = -ty / length
        ny = -tx / length

    if flip_y:
        nx = -nx
        ny = -ny

    # Anchor: displaced by offset_dist along the chosen normal direction
    sx = x_rod + nx * offset_dist
    sy = y_rod + ny * offset_dist

    # Local X axis is perpendicular to normal (so X × Y = Z)
    xx = ny
    xy = -nx

    pts_2d = []
    for lp in local_pts:
        rx = lp[0] * xx + lp[1] * nx + sx
        ry = lp[0] * xy + lp[1] * ny + sy
        pts_2d.append([rx, ry])
    return pts_2d
