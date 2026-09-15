"""
Wing section geometry builder using build123d.

Produces separate Part objects for each render target:
  - part              : main solid (male peg + female sleeve if applicable)
  - bell_modifier     : bell-groove volumes around full-run rods
  - rod_joint_modifier: ellipse volumes spanning each joined rod pair
  - sleeve_modifier   : flat box covering female sleeve zone (female sections only)

With `construction="omega"` the rods sit on the skin and the targets are:
  - part              : main solid with an omega pocket cut for every rod
  - walls             : the modelled walls -- omega clips (feet + loop) and the
                        front/rear box webs -- clipped to the part
  - le_cell_modifier  : LE -> front web
  - box_cell_modifier : front web -> rear web
  - te_cell_modifier  : rear web -> TE
  - rod_joint_modifier: capsule over each lapping rod pair, (1 + margin) x rod
  - sleeve_modifier   : as above
"""
import sys
import math
from build123d import Vector, Solid, Location

from .geometry.profiles import bell_pts, capsule_pts, ellipse_pts, place_at_normal
from .geometry.shapes import (
    compound_list, fuse_all, loft_solid, make_wire3d, naca_wire, naca_wire_offset,
    rod_cylinder,
)
from .section_layout import SectionInfo, WingDefinition, chord_at, omega_rod_frame


def _collect_rod_cutters(sec: SectionInfo, wing: WingDefinition) -> list:
    """All rod-hole cylinders for this section (local z coords)."""
    r = wing.rod_diameter / 2
    holes_solid = []
    
    for h in sec.holes:
        # Upper rod
        holes_solid.append(rod_cylinder(h.x0, h.yu0, h.x1, h.yu1, h.z0, h.z1, r))
        # Lower rod
        holes_solid.append(rod_cylinder(h.x0, h.yl0, h.x1, h.yl1, h.z0, h.z1, r))

    return holes_solid


# ─────────────────────────────────────────────────────────────
# Per-section geometry builders
# ─────────────────────────────────────────────────────────────

def _build_main_solid(sec: SectionInfo, wing: WingDefinition) -> Solid:
    """
    Main structural solid for the section (local z: 0=root face, L=tip face).
    Includes male peg at tip and/or female sleeve at root if applicable.
    """
    L = sec.z_end - sec.z_start
    c0 = chord_at(sec.z_start, wing)
    c1 = chord_at(sec.z_end,   wing)

    jt    = wing.joint_thickness
    cl    = wing.clearance
    eg    = wing.epoxy_gap
    ag    = wing.axial_gap
    jl    = wing.joint_length
    peg_inset = jt + cl + eg  # total inward offset for male peg

    parts = []

    # ── Female sleeve extending below z=0 ──
    if sec.female_at_root:
        # Sleeve = full outer profile from z=-joint_length to z=-1
        # (constant chord = chord of THIS section at z_start)
        w_sl0 = naca_wire(wing.naca, c0, -jl)
        w_sl1 = naca_wire(wing.naca, c0, -1.0)
        sleeve = loft_solid([w_sl0, w_sl1])
        parts.append(sleeve)

        # 1mm CAD void ring at z=0 ( gap between sleeve and main body)
        # → thin shell ring just inside body to avoid z-fighting
        # We represent it as a difference: full disc minus inner disc at z=-1..0
        ring_outer = loft_solid([naca_wire(wing.naca, c0, -1.0),
                                   naca_wire(wing.naca, c0,  0.0)])
        ring_inner = loft_solid([naca_wire_offset(wing.naca, c0, -1.0, jt),
                                   naca_wire_offset(wing.naca, c0,  0.0, jt)])
        void_ring = ring_outer - ring_inner
        parts.append(void_ring)

    # ── Main body (root face to peg-start or full if no tip joint) ──
    if sec.male_at_tip:
        body_end = L - jl
    else:
        body_end = L

    w0 = naca_wire(wing.naca, c0, 0.0)
    w1 = naca_wire(wing.naca, chord_at(sec.z_start + body_end, wing), body_end)
    body = loft_solid([w0, w1])
    parts.append(body)

    # ── Male peg at tip ──
    if sec.male_at_tip:
        peg_z0 = L - jl
        peg_z1 = L - ag
        c_peg0 = chord_at(sec.z_start + peg_z0, wing)
        c_peg1 = chord_at(sec.z_start + peg_z1, wing)
        w_p0 = naca_wire_offset(wing.naca, c_peg0, peg_z0, peg_inset)
        w_p1 = naca_wire_offset(wing.naca, c_peg1, peg_z1, peg_inset)
        peg = loft_solid([w_p0, w_p1])
        parts.append(peg)

    # Merge all parts
    solid = parts[0]
    for p in parts[1:]:
        solid = solid + p

    return solid


# Removed complex overlapping logic and interpolations, now handled in section_layout


# ─────────────────────────────────────────────────────────────
# Modifier builders
# ─────────────────────────────────────────────────────────────

def _build_bell_modifier(sec: SectionInfo, wing: WingDefinition) -> list:
    """
    Bell-profile modifier solids along the PRIMARY rods.
    One body per rod (upper + lower), lofted between z0 and z1.
    """
    bell_local = bell_pts(wing.bell_width, wing.bell_height, wing.bell_shape)
    solids = []

    for h in sec.holes:
        if not h.is_primary:
            continue
            
        for sign, y0, y1 in [(+1, h.yu0, h.yu1), (-1, h.yl0, h.yl1)]:
            pts0_2d = place_at_normal(h.x0, y0, h.chord0, wing.naca,
                                       sign, h.z0, wing.bell_offset, bell_local)
            pts_3d0 = [[p[0], p[1], h.z0] for p in pts0_2d]
            
            pts1_2d = place_at_normal(h.x1, y1, h.chord1, wing.naca,
                                       sign, h.z1, wing.bell_offset, bell_local)
            pts_3d1 = [[p[0], p[1], h.z1] for p in pts1_2d]

            w0 = make_wire3d(pts_3d0)
            w1 = make_wire3d(pts_3d1)
            try:
                solids.append(loft_solid([w0, w1]))
            except Exception:
                pass

    return solids


def _build_rod_joint_modifier(sec: SectionInfo, wing: WingDefinition) -> list:
    """
    Ellipse spanning each pair of rods that hand over load at the overlap zone,
    extruded over the length of that overlap. One body per pair, per deck.
    """
    solids = []

    for mod in sec.joint_mods:
        pts = ellipse_pts(mod.xa, mod.ya, mod.xb, mod.yb, wing.joint_mod_thickness)
        w0 = make_wire3d([[p[0], p[1], mod.z0] for p in pts])
        w1 = make_wire3d([[p[0], p[1], mod.z1] for p in pts])
        try:
            solids.append(loft_solid([w0, w1]))
        except Exception:
            pass

    return solids


def _build_sleeve_modifier(sec: SectionInfo, wing: WingDefinition) -> list:
    """
    Box covering the female sleeve zone (z = -joint_length to z = -1).
    Used as a PrusaSlicer modifier volume for sleeve print settings.
    Female sections only.
    """
    if not sec.female_at_root:
        return []

    c0 = chord_at(sec.z_start, wing)
    jl = wing.joint_length
    bw = c0 + 10.0
    bh = c0 * 0.15 + 10.0

    # Box from z=-jl to z=-1  (centred around section root face)
    box_solid = Solid.make_box(bw, bh, jl - 1.0).move(
        Location(Vector(-bw / 2, -bh / 2, -jl)))
    return [box_solid]


# ─────────────────────────────────────────────────────────────
# Omega construction
# ─────────────────────────────────────────────────────────────
#
def _omega_local(wing: WingDefinition, n_arc: int = 16):
    """(pocket, wall) profiles in the local (t, n) frame."""
    om = wing.omega
    r = wing.rod_diameter / 2
    rho = r + om.omega_clearance
    w = om.omega_wall
    h = om.omega_neck_width / 2 if om.omega_neck_width is not None else r
    h = max(h, math.sqrt(max(rho ** 2 - r ** 2, 0.0)) + 0.01)   # neck must sit outside the loop

    # tangent from the neck (h, 0) onto the loop, on its far-side branch
    dist = math.hypot(h, r)
    theta_r = math.atan2(-r, h) + math.acos(rho / dist)
    theta_l = math.pi - theta_r

    def arc(radius, a0, a1):
        # circumscribed, so the facets never cut into the rod's fit envelope
        radius /= math.cos((a1 - a0) / n_arc / 2)
        return [(radius * math.cos(a0 + (a1 - a0) * i / n_arc),
                 r + radius * math.sin(a0 + (a1 - a0) * i / n_arc)) for i in range(n_arc + 1)]

    inner = arc(rho, theta_r, theta_l)               # right tangent point -> over the top -> left
    outer = arc(rho + w, theta_r, theta_l)
    if outer[0][1] < w + 1e-3:
        raise ValueError(f"omega_neck_width {2 * h:.2f} mm is too narrow: the clip's outer "
                         f"face would run back into its own foot")

    # outer face of the right leg, continued down to the top of the foot (n = w)
    seg = (h - inner[0][0], -inner[0][1])
    seg_len = math.hypot(*seg)
    seg = (seg[0] / seg_len, seg[1] / seg_len)
    s_foot = (w - outer[0][1]) / seg[1]
    f_t = outer[0][0] + s_foot * seg[0]
    t_foot = f_t + om.omega_foot_length

    pocket = [(h, 0.0)] + inner + [(-h, 0.0)]
    wall = ([(t_foot, 0.0), (t_foot, w), (f_t, w)] + outer
            + [(-f_t, w), (-t_foot, w), (-t_foot, 0.0), (-h, 0.0)]
            + inner[::-1] + [(h, 0.0)])
    return pocket, wall


def _omega_place(local: list, wing: WingDefinition, pct: float, chord: float,
                 upper: bool, z: float) -> list:
    """Local (t, n) profile -> section xyz at height z, for one rod."""
    cx, cy, nx, ny = omega_rod_frame(wing, pct, chord, upper)
    r = wing.rod_diameter / 2
    mx, my = -nx, -ny                          # into the wing
    tx, ty = my, -mx                           # t x n = +z, so CCW stays CCW
    ox, oy = cx - r * mx, cy - r * my          # T, on the skin inner face
    return [[ox + t * tx + n * mx, oy + t * ty + n * my, z] for t, n in local]


def _omega_rod_solids(sec: SectionInfo, wing: WingDefinition):
    pocket_local, wall_local = _omega_local(wing)
    pockets, walls = [], []
    for h in sec.holes:
        for upper in (True, False):
            for local, out in ((pocket_local, pockets), (wall_local, walls)):
                w0 = make_wire3d(_omega_place(local, wing, h.pct, h.chord0, upper, h.z0))
                w1 = make_wire3d(_omega_place(local, wing, h.pct, h.chord1, upper, h.z1))
                out.append(loft_solid([w0, w1]))
    return pockets, walls


def _chord_box(sec: SectionInfo, wing: WingDefinition, pct0: float, pct1: float,
               pad0: float = 0.0, pad1: float = 0.0):
    """Prism between two chord fractions (+ absolute pads in mm), full depth, z 0..L.

    Bounds are chord fractions, so the prism tapers with the wing and a web at a
    fixed fraction stays a fixed fraction of the chord all along the section.
    """
    L = sec.z_end - sec.z_start
    wires = []
    for z in (0.0, L):
        c = chord_at(sec.z_start + z, wing)
        x0, x1 = (pct0 - 0.5) * c + pad0, (pct1 - 0.5) * c + pad1
        y = 0.3 * c
        wires.append(make_wire3d([[x0, -y, z], [x1, -y, z], [x1, y, z], [x0, y, z]]))
    return loft_solid(wires)



def _build_omega_joint_modifier(sec: SectionInfo, wing: WingDefinition) -> list:
    radius = (1.0 + wing.omega.joint_mod_margin_pct) * wing.rod_diameter / 2
    solids = []
    for m in sec.joint_mods:
        p0 = capsule_pts(m.xa, m.ya, m.xb, m.yb, radius)
        p1 = capsule_pts(m.xa1, m.ya1, m.xb1, m.yb1, radius)
        w0 = make_wire3d([[p[0], p[1], m.z0] for p in p0])
        w1 = make_wire3d([[p[0], p[1], m.z1] for p in p1])
        solids.append(loft_solid([w0, w1]))
    return solids


def build_all_omega(sec: SectionInfo, wing: WingDefinition) -> dict:
    om = wing.omega
    t_half = om.box_wall / 2
    result = {}

    solid = _build_main_solid(sec, wing)
    pockets, clip_walls = _omega_rod_solids(sec, wing)
    pocket = fuse_all(pockets)
    if pocket is not None:
        solid = solid - pocket
    result['part'] = solid

    webs = [_chord_box(sec, wing, pct, pct, -t_half, t_half)
            for pct in (om.front_web_pct, om.rear_web_pct)]
    walls = fuse_all(clip_walls + webs)
    result['walls'] = solid.intersect(walls)

    result['le_cell_modifier'] = _chord_box(sec, wing, 0.0, om.front_web_pct, -2.0, -t_half)
    result['box_cell_modifier'] = _chord_box(sec, wing, om.front_web_pct, om.rear_web_pct, t_half, -t_half)
    result['te_cell_modifier'] = _chord_box(sec, wing, om.rear_web_pct, 1.0, t_half, 2.0)

    result['rod_joint_modifier'] = compound_list(_build_omega_joint_modifier(sec, wing))
    result['sleeve_modifier'] = compound_list(_build_sleeve_modifier(sec, wing))
    return result


# ─────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────

def build_all(sec: SectionInfo, wing: WingDefinition) -> dict:
    """
    Build all geometry for a section.
    Returns dict keyed by render-target name → Solid or Compound or None.

    Render targets:
      'part'              – main structural solid with rod holes subtracted
      'bell_modifier'     – bell-groove modifier volumes (primary rods)
      'rod_joint_modifier'– ellipse modifier spanning each joined rod pair
      'sleeve_modifier'   – flat box at female joint zone

    `construction="omega"` returns a different set; see `build_all_omega`.
    """
    if wing.construction == "omega":
        return build_all_omega(sec, wing)
    result = {}

    # ── Main solid ──
    solid = _build_main_solid(sec, wing)
    hole_cutters = _collect_rod_cutters(sec, wing)
    for h in hole_cutters:
        try:
            solid = solid - h
        except Exception as e:
            print(f"  [WARN] rod hole subtraction failed: {e}", file=sys.stderr)
    result['part'] = solid

    # ── Bell modifier ──
    bells = _build_bell_modifier(sec, wing)
    result['bell_modifier'] = compound_list(bells)

    # ── Rod joint modifier ──
    rod_mods = _build_rod_joint_modifier(sec, wing)
    result['rod_joint_modifier'] = compound_list(rod_mods)

    # ── Sleeve modifier (female only) ──
    sleeve_mods = _build_sleeve_modifier(sec, wing)
    result['sleeve_modifier'] = compound_list(sleeve_mods)

    return result
