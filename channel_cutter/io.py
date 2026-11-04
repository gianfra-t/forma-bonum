from __future__ import annotations

from pathlib import Path

from build123d import Mesher, Shape, Solid, export_step, import_step
from OCP.BRep import BRep_Tool
from OCP.BRepMesh import BRepMesh_IncrementalMesh
from OCP.BRepTools import BRepTools
from OCP.StlAPI import StlAPI_Writer
from OCP.TopLoc import TopLoc_Location


def load_solid(path) -> Solid:
    path = Path(path)
    ext = path.suffix.lower()
    if ext in (".step", ".stp"):
        shapes = [import_step(path)]
    elif ext == ".stl":
        shapes = Mesher().read(path)
    else:
        raise ValueError(f"unsupported file type: {path.name}")
    solids = [s for shape in shapes for s in shape.solids()]
    if len(solids) != 1:
        raise ValueError(f"{path.name}: expected one solid, found {len(solids)}")
    return solids[0]


def export(shape: Shape, path, deflection: float = 0.02, angle: float = 0.2) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix.lower() in (".step", ".stp"):
        export_step(shape, path)
        return
    for d, a in ((deflection * 2 ** k, angle * 2 ** k) for k in range(4)):
        BRepTools.Clean_s(shape.wrapped)
        BRepMesh_IncrementalMesh(shape.wrapped, d, False, a, True)
        if all(BRep_Tool.Triangulation_s(f.wrapped, TopLoc_Location()) is not None or abs(f.area) < 1e-6
               for f in shape.faces()):
            break
    else:
        raise RuntimeError(f"{path.name}: a face does not mesh even at {d} mm, {a} rad")
    writer = StlAPI_Writer()
    writer.ASCIIMode = False
    writer.Write(shape.wrapped, str(path))
