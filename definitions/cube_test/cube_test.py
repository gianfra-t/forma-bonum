
from pathlib import Path

from build123d import Box, Cylinder, export_stl

SIDE = 20.0
HOLE_MIN = 2.00
HOLE_MAX = 2.30
HOLE_STEP = 0.05

OUT = Path(__file__).resolve().parent / "output"


def diameters() -> list[float]:
    n = round((HOLE_MAX - HOLE_MIN) / HOLE_STEP)
    return [round(HOLE_MIN + i * HOLE_STEP, 2) for i in range(n + 1)]


def cube(d: float):
    """Cube centred on the origin, hole along z through both faces."""
    return Box(SIDE, SIDE, SIDE) - Cylinder(d / 2, SIDE)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    for d in diameters():
        path = OUT / f"cube_hole_{d:.2f}.stl"
        export_stl(cube(d), path)
        print(f"  ok  {path.name}")
