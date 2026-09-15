"""NACA 4-digit profile utilities."""
from functools import lru_cache
from pathlib import Path

import numpy as np
from shapely.geometry import Polygon

# Selig .dat files for non-4-digit sections live beside the package.
AIRFOIL_DIR = Path(__file__).parent / "airfoils"


def naca4_yt(t: float, x: np.ndarray) -> np.ndarray:
    """Thickness distribution (half-thickness at chord fraction x)."""
    return 5 * t * (0.2969 * np.sqrt(x) - 0.1260 * x - 0.3516 * x**2
                    + 0.2843 * x**3 - 0.1015 * x**4)


def naca4_camber(m: float, p: float, x: np.ndarray):
    """Camber line and slope for NACA 4-digit."""
    yc = np.where(x < p,
                  m / p**2 * (2 * p * x - x**2),
                  m / (1 - p)**2 * ((1 - 2 * p) + 2 * p * x - x**2))
    dyc = np.where(x < p,
                   2 * m / p**2 * (p - x),
                   2 * m / (1 - p)**2 * (p - x))
    return yc, dyc


def naca4_points(digits: str, n: int = 80):
    """
    Return (upper_pts, lower_pts) in chord-fraction coords [0..1].
    upper/lower are numpy arrays of shape (n, 2).
    """
    if not (digits.isdigit() and len(digits) == 4):
        import urllib.request
        # Resolve against the package's own airfoils/ dir, not the cwd, so a
        # shipped .dat is found no matter where the generator is run from.
        filename = AIRFOIL_DIR / f"{digits}.dat"
        if not filename.exists():
            print(f"Downloading airfoil dat for {digits}...")
            url = f"http://airfoiltools.com/airfoil/seligdatfile?airfoil={digits}"
            try:
                AIRFOIL_DIR.mkdir(parents=True, exist_ok=True)
                urllib.request.urlretrieve(url, filename)
            except Exception as e:
                raise ValueError(f"Failed to fetch {digits}.dat from airfoiltools.com: {e}")

        with open(filename, "r") as f:
            lines = f.readlines()
            
        pts = []
        for line in lines[1:]: # skip header
            parts = line.strip().split()
            if len(parts) == 2:
                try:
                    pts.append([float(parts[0]), float(parts[1])])
                except Exception:
                    pass
        pts = np.array(pts)
        min_idx = np.argmin(pts[:, 0])
        
        upper_raw = pts[:min_idx+1]
        lower_raw = pts[min_idx:]
        
        upper = upper_raw[::-1]
        lower = lower_raw

        beta = np.linspace(0, np.pi, n)
        x_new = (1 - np.cos(beta)) / 2.0
        
        u_idx = np.unique(upper[:,0], return_index=True)[1]
        upper = upper[np.sort(u_idx)]
        
        l_idx = np.unique(lower[:,0], return_index=True)[1]
        lower = lower[np.sort(l_idx)]

        y_up = np.interp(x_new, upper[:, 0], upper[:, 1])
        y_low = np.interp(x_new, lower[:, 0], lower[:, 1])

        return np.column_stack((x_new, y_up)), np.column_stack((x_new, y_low))

    m = int(digits[0]) / 100.0
    p = int(digits[1]) / 10.0
    t = int(digits[2:]) / 100.0

    beta = np.linspace(0, np.pi, n)
    x = (1 - np.cos(beta)) / 2.0  # cosine spacing

    yt = naca4_yt(t, x)

    if m == 0 and p == 0:
        yc = np.zeros_like(x)
        theta = np.zeros_like(x)
    else:
        yc, dyc = naca4_camber(m, p, x)
        theta = np.arctan(dyc)

    xu = x - yt * np.sin(theta)
    yu = yc + yt * np.cos(theta)
    xl = x + yt * np.sin(theta)
    yl = yc - yt * np.cos(theta)

    upper = np.column_stack([xu, yu])
    lower = np.column_stack([xl, yl])
    return upper, lower


def naca4_polygon_pts(digits: str, chord: float, n: int = 60) -> list:
    """
    Closed polygon of NACA profile, scaled to chord (mm).
    Centered so leading edge at x=-chord/2, trailing edge at x=+chord/2.
    Returns list of [x, y] pairs suitable for Shapely / build123d.
    """
    upper, lower = naca4_points(digits, n)
    # scale and center
    def sc(pts):
        return [[p[0] * chord - chord / 2, p[1] * chord] for p in pts]

    u = sc(upper)  # LE to TE on top
    l = sc(lower)  # LE to TE on bottom
    # Closed: upper forward, lower reversed back to LE (skip duplicate LE/TE)
    poly = u + list(reversed(l[1:-1]))
    return poly


def naca4_y_at(digits: str, x_frac: float, n: int = 200) -> float:
    """
    Upper-surface Y at chord fraction x_frac [0..1] (positive half-thickness).
    Returns value in chord-fraction units.
    """
    upper, _ = naca4_points(digits, n)
    # upper[:,0] is sorted roughly 0..1, interpolate
    return float(np.interp(x_frac, upper[:, 0], upper[:, 1]))


def naca4_y_lower_at(digits: str, x_frac: float, n: int = 200) -> float:
    """
    Lower-surface Y at chord fraction x_frac [0..1].
    Returns value in chord-fraction units.
    """
    _, lower = naca4_points(digits, n)
    return float(np.interp(x_frac, lower[:, 0], lower[:, 1]))


def offset_polygon(pts: list, offset: float) -> list:
    """
    Inward polygon offset using Shapely.
    offset > 0 = shrink inward, offset < 0 = expand outward.
    Returns list of [x, y].
    """
    poly = Polygon(pts)
    buffered = poly.buffer(-offset, join_style=2)  # join_style=2 = mitre
    if buffered.is_empty:
        raise ValueError(f"Offset polygon collapsed (offset={offset})")
    coords = list(buffered.exterior.coords)[:-1]  # drop closing duplicate
    return [[c[0], c[1]] for c in coords]


@lru_cache(maxsize=None)
def _surface_table(digits: str, n: int = 801):
    """Dense (upper, lower) tables, cached: the omega layout samples them a lot."""
    return naca4_points(digits, n)


def surface_point_normal(digits: str, x_frac: float, upper: bool,
                         dx: float = 1e-3) -> tuple[float, float, float, float]:
    """Skin point and OUTWARD unit normal at chord fraction x_frac.

    Returns (x, y, nx, ny), point in chord-fraction units, LE at x=0. The normal
    is scale-free, so it holds at any chord.
    """
    up, lo = _surface_table(digits)
    pts = up if upper else lo
    y = float(np.interp(x_frac, pts[:, 0], pts[:, 1]))
    slope = (float(np.interp(x_frac + dx, pts[:, 0], pts[:, 1]))
             - float(np.interp(x_frac - dx, pts[:, 0], pts[:, 1]))) / (2 * dx)
    length = float(np.hypot(1.0, slope))
    if upper:
        return x_frac, y, -slope / length, 1.0 / length
    return x_frac, y, slope / length, -1.0 / length


def rod_y_upper(digits: str, x_frac: float, chord: float,
                skin_dist: float, rod_r: float) -> float:
    """Upper rod centre Y (mm, centered coords) at chord fraction x_frac."""
    y_surf = naca4_y_at(digits, x_frac) * chord
    return y_surf - skin_dist - rod_r


def rod_y_lower(digits: str, x_frac: float, chord: float,
                skin_dist: float, rod_r: float) -> float:
    """Lower rod centre Y (mm, centered coords) at chord fraction x_frac."""
    y_surf = naca4_y_lower_at(digits, x_frac) * chord
    return y_surf + skin_dist + rod_r


def fits_inside(x_centered: float, chord: float, digits: str,
                skin_dist: float, rod_r: float) -> bool:
    """Return True if upper AND lower rod fit inside the profile."""
    x_frac = x_centered / chord + 0.5
    if x_frac <= 0.01 or x_frac >= 0.99:
        return False
    y_u = rod_y_upper(digits, x_frac, chord, skin_dist, rod_r)
    y_l = rod_y_lower(digits, x_frac, chord, skin_dist, rod_r)
    return y_u > rod_r and y_l < -rod_r and (y_u - y_l) > 2 * rod_r + 1.0
