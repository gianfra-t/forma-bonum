"""Section layout algorithm for tapered wing generator."""
from __future__ import annotations
import math
from dataclasses import dataclass, field
from typing import Optional
from .naca import (fits_inside, naca4_y_at, rod_y_upper, rod_y_lower,
                   surface_point_normal)


# ──────────────────────────────────────────────────────────────
# Data definitions
# ──────────────────────────────────────────────────────────────

@dataclass
class RodSection:
    chord_pcts: list[float]    # chord fractions (0=LE, 1=TE)


@dataclass
class OmegaSettings:
    """Parameters of the `construction="omega"` mode.

    Rods sit tangent to the inside of the skin instead of in a bore
    `skin_distance` below it, and each is held by an omega-shaped wall: two feet
    on the skin either side of the rod, a loop around it. Walls are multiples of
    one extrusion, `line_width`. Spanwise front and rear webs close a torsion box.
    """
    line_width: float = 0.42
    skin_lines: int = 1                  # skin the rods bear on
    omega_lines: int = 1                 # clip wall
    omega_clearance: float = 0.0         # rod envelope -> clip inner face (rod_diameter is already the fit envelope)
    omega_neck_width: Optional[float] = None  # where the clip's inner face leaves the skin; None = rod_diameter
    omega_foot_length: float = 1.0       # foot run along the skin beyond the clip's outer face
    rod_min_gap: float = 0.5             # rod surface to rod surface, same deck
    snap_to_previous: bool = True        # pull outboard rods to rod_min_gap off an inboard rod
    joint_mod_margin_pct: float = 0.20   # lap modifier covers both rods at (1 + this) x diameter, and the gap
    box_le_pct: float = 0.20             # front web, chord fraction from the LE
    box_te_pct: float = 0.30             # rear web, chord fraction from the TE
    box_wall_lines: int = 1

    @property
    def skin_wall(self) -> float:
        return self.skin_lines * self.line_width

    @property
    def omega_wall(self) -> float:
        return self.omega_lines * self.line_width

    @property
    def box_wall(self) -> float:
        return self.box_wall_lines * self.line_width

    @property
    def front_web_pct(self) -> float:
        return self.box_le_pct

    @property
    def rear_web_pct(self) -> float:
        return 1.0 - self.box_te_pct


@dataclass
class WingDefinition:
    span: float
    root_chord: float
    tip_chord: float
    naca: str
    rod_length: float          # physical length of the rod (e.g. 1000.0 or 250.0)
    rod_multiple: int          # how many print sections fit in one rod span
    rod_overlap_pct: float     # rod overlap per side (e.g. 0.05)
    rod_diameter: float
    skin_distance: float
    joint_length: float
    joint_thickness: float
    clearance: float
    epoxy_gap: float
    axial_gap: float
    rod_sections: list[RodSection]
    min_x_separation_pct: float = 0.25   # % of diameter for x-overlap clearance
    min_y_separation_pct: float = 0.8    # % of diameter for collision handling
    bell_width:  float = 10.0
    bell_height: float = 7.0
    bell_offset: float = -3.0
    bell_shape:  float = 3.5
    joint_mod_thickness: float = 12.0   # minor axis of the rod-joint ellipse
    construction: str = "bore"          # "bore" (rod in a bore under the skin) | "omega"
    omega: OmegaSettings = field(default_factory=OmegaSettings)

    def __post_init__(self):
        if self.construction not in ("bore", "omega"):
            raise ValueError(f"construction must be 'bore' or 'omega', got {self.construction!r}")
        if self.construction == "omega" and not (
                0.0 < self.omega.front_web_pct < self.omega.rear_web_pct < 1.0):
            raise ValueError("omega box webs must satisfy 0 < box_le_pct < 1 - box_te_pct < 1")


@dataclass
class SectionRodHole:
    z0: float              # local Z start
    z1: float              # local Z end
    x0: float
    yu0: float
    yl0: float
    chord0: float          # for computing normal in builder
    x1: float
    yu1: float
    yl1: float
    chord1: float
    is_primary: bool
    # omega construction only: upper and lower rods no longer share x, and the
    # builder rebuilds the clip frame from the rod's chord fraction.
    xl0: Optional[float] = None
    xl1: Optional[float] = None
    pct: Optional[float] = None


@dataclass
class SectionJointMod:
    """Solid-infill zone bridging two rods that hand over the load at a joint.

    (xa, ya) and (xb, yb) are the two rod centres; the builder wraps an ellipse
    around that segment. Rods run parallel to z, so one pair of points serves the
    whole z0..z1 extent.
    """
    z0: float
    z1: float
    xa: float
    ya: float
    xb: float
    yb: float
    # omega construction only: rods follow the tapering skin, so the centres at
    # z1 differ from z0. None = same as at z0.
    xa1: Optional[float] = None
    ya1: Optional[float] = None
    xb1: Optional[float] = None
    yb1: Optional[float] = None


@dataclass
class SectionInfo:
    index: int
    z_start: float             # global spanwise start (mm from root)
    z_end: float               # global spanwise end
    female_at_root: bool       # sleeve joint at root face
    male_at_tip: bool          # peg at tip face
    holes: list[SectionRodHole]
    joint_mods: list[SectionJointMod]


# ──────────────────────────────────────────────────────────────
# Structural Rod Computations
# ──────────────────────────────────────────────────────────────

@dataclass
class ComputedRod:
    abs_x: float
    abs_yu: float
    abs_yl: float
    z_cut_off: float
    # omega construction only
    pct: Optional[float] = None            # placed chord fraction, constant along the rod
    requested_pct: Optional[float] = None
    partner: Optional[int] = None          # index of the inboard rod it was snapped to

@dataclass
class PhysicalRodSection:
    r: int
    z_bounds_start: float
    z_bounds_end: float
    rods: list[ComputedRod]


def chord_at(z: float, wing: WingDefinition) -> float:
    t = max(0.0, min(1.0, z / wing.span))
    return wing.root_chord + (wing.tip_chord - wing.root_chord) * t


def _compute_physical_rod_sections(wing: WingDefinition) -> list[PhysicalRodSection]:
    if wing.construction == "omega":
        return _compute_omega_rod_sections(wing)
    L_eff = wing.rod_length * (1.0 - 2.0 * wing.rod_overlap_pct)
    rod_depth = wing.rod_length * wing.rod_overlap_pct
    n_rod_float = wing.span / L_eff
    n_rod_whole = int(n_rod_float)
    frac = n_rod_float - n_rod_whole
    n_rod = n_rod_whole + (1 if frac > 0.0 else 0)

    if len(wing.rod_sections) != n_rod:
        raise ValueError(f"Expected exactly {n_rod} section placements in rod_sections for span {wing.span} and rod length {wing.rod_length}, but got {len(wing.rod_sections)}.")

    computed = []
    
    for r in range(n_rod):
        user_pcts = wing.rod_sections[r].chord_pcts
            
        z_start_nominal = r * L_eff

        # bounds — per rod span, not per rod, so an empty chord_pcts (a span with no
        # rods at all) still gets well-defined bounds instead of the previous span's
        z_bounds_start = max(0.0, r * L_eff - rod_depth)
        z_bounds_end = min(wing.span, (r + 1) * L_eff + rod_depth)

        computed_rods_abs = []
        for j, raw_pct in enumerate(user_pcts):
            pct = raw_pct

            rod_r = wing.rod_diameter / 2
            min_y_sep = wing.rod_diameter * (1.0 + wing.min_y_separation_pct)
            
            # Handle collisions iteratively
            max_iters = 100
            for _ in range(max_iters):
                c_start = chord_at(z_start_nominal, wing)
                x = (pct - 0.5) * c_start
                
                collision = False
                
                # Compare with previous section
                if r > 0:
                    for prev_rod in computed[r-1].rods:
                        if abs(x - prev_rod.abs_x) < min_y_sep:
                            collision = True
                            break
                            
                # Compare with same section previously placed rods
                if not collision:
                    for prev_same_rod in computed_rods_abs:
                        if abs(x - prev_same_rod.abs_x) < min_y_sep:
                            collision = True
                            break
                            
                if not collision:
                    break
                    
                # If colliding, move rod closest to the tip (the current one in section r, or the current j)
                if pct < 0.33:
                    pct -= 0.01  # go to leading edge
                else:
                    pct += 0.01  # go to trailing edge
            
            final_c_start = chord_at(z_start_nominal, wing)
            x = (pct - 0.5) * final_c_start
            
            # Secondary Objective: compute max y distance at z_bounds_end and do not cut it.
            z_cut = z_bounds_end
            c_cut = chord_at(z_cut, wing)
            pct_cut = (x / c_cut) + 0.5
            
            yu = rod_y_upper(wing.naca, pct_cut, c_cut, wing.skin_distance, rod_r)
            yl = rod_y_lower(wing.naca, pct_cut, c_cut, wing.skin_distance, rod_r)
            
            computed_rods_abs.append(ComputedRod(abs_x=x, abs_yu=yu, abs_yl=yl, z_cut_off=z_cut))
            
        computed.append(PhysicalRodSection(r=r, z_bounds_start=z_bounds_start,
                                           z_bounds_end=z_bounds_end, 
                                           rods=computed_rods_abs))
        
    return computed


# ──────────────────────────────────────────────────────────────
# Omega construction: rods tangent to the skin
# ──────────────────────────────────────────────────────────────

def omega_skin_offset(wing: WingDefinition) -> float:
    """Outer surface -> the face the rod bears on.

    The skin wall, or the sleeve wall where the rod crosses a joint if that is
    thicker: the rod is straight, so it has to clear both.
    """
    return max(wing.omega.skin_wall, wing.joint_thickness)


def omega_rod_frame(wing: WingDefinition, pct: float, chord: float, upper: bool):
    """Rod centre and outward skin normal for a skin-tangent rod.

    Returns (cx, cy, nx, ny) in section coordinates (mm, mid-chord at x=0). The
    centre is the skin point pushed inward by skin offset + rod radius along the
    normal. Everything but the chord is scale-free, so at a fixed `pct` the
    centre is linear in chord -- a straight rod stays tangent along a linear taper.
    """
    xf, yf, nx, ny = surface_point_normal(wing.naca, pct, upper)
    d = omega_skin_offset(wing) + wing.rod_diameter / 2
    return (xf - 0.5) * chord - d * nx, yf * chord - d * ny, nx, ny


def _omega_centres(wing: WingDefinition, pct: float, chord: float):
    xu, yu, _, _ = omega_rod_frame(wing, pct, chord, True)
    xl, yl, _, _ = omega_rod_frame(wing, pct, chord, False)
    return (xu, yu), (xl, yl)


def _omega_gap(wing: WingDefinition, pa: float, pb: float,
               z0: float, z1: float) -> float:
    """Smallest rod-surface gap between pairs at pa and pb over [z0, z1], worst deck.

    Centre = chord * A(pct) + B(pct), so the separation is |c*u + v|, convex in
    the chord: its minimum is analytic.
    """
    c0, c1 = chord_at(z0, wing), chord_at(z1, wing)
    lo, hi = min(c0, c1), max(c0, c1)
    gap = math.inf
    for upper in (True, False):
        a0 = omega_rod_frame(wing, pa, 0.0, upper)
        a1 = omega_rod_frame(wing, pa, 1.0, upper)
        b0 = omega_rod_frame(wing, pb, 0.0, upper)
        b1 = omega_rod_frame(wing, pb, 1.0, upper)
        v = (a0[0] - b0[0], a0[1] - b0[1])                     # chord-independent part
        u = (a1[0] - b1[0] - v[0], a1[1] - b1[1] - v[1])       # per-mm-of-chord part
        uu = u[0] ** 2 + u[1] ** 2
        c = lo if uu < 1e-12 else min(hi, max(lo, -(u[0] * v[0] + u[1] * v[1]) / uu))
        gap = min(gap, math.hypot(c * u[0] + v[0], c * u[1] + v[1]) - wing.rod_diameter)
    return gap


@dataclass
class _Placed:
    pct: float
    z0: float
    z1: float


def _omega_fits(wing: WingDefinition, pct: float, z0: float, z1: float) -> bool:
    """Pair clear of LE/TE, and the upper rod clear of the lower one."""
    if not (0.02 <= pct <= 0.98):
        return False
    for z in (z0, z1):
        (xu, yu), (xl, yl) = _omega_centres(wing, pct, chord_at(z, wing))
        if math.hypot(xu - xl, yu - yl) - wing.rod_diameter < wing.omega.rod_min_gap:
            return False
    return True


def _omega_web_clearance(wing: WingDefinition, pct: float, z0: float, z1: float) -> dict[str, float]:
    """Clip loop to box web, mm, per web, at the tighter end (negative = crossing)."""
    om = wing.omega
    reach = wing.rod_diameter / 2 + om.omega_clearance + om.omega_wall + om.box_wall / 2
    out = {}
    for name, wp in (("front", om.front_web_pct), ("rear", om.rear_web_pct)):
        clear = math.inf
        for z in (z0, z1):
            c = chord_at(z, wing)
            for xc, _ in _omega_centres(wing, pct, c):
                clear = min(clear, abs(xc - (wp - 0.5) * c) - reach)
        out[name] = clear
    return out


def _omega_clear(wing: WingDefinition, pct: float, z0: float, z1: float,
                 others: list[_Placed], webs: bool = True) -> bool:
    if not _omega_fits(wing, pct, z0, z1):
        return False
    if webs and min(_omega_web_clearance(wing, pct, z0, z1).values()) < 0:
        return False
    for o in others:
        oz0, oz1 = max(z0, o.z0), min(z1, o.z1)
        if oz1 > oz0 + 0.01 and _omega_gap(wing, pct, o.pct, oz0, oz1) < wing.omega.rod_min_gap - 1e-6:
            return False
    return True


def _omega_snap(wing: WingDefinition, partner: _Placed, side: int,
                z0: float, z1: float) -> Optional[float]:
    """Chord fraction on `side` of `partner` at exactly rod_min_gap from it."""
    oz0, oz1 = max(z0, partner.z0), min(z1, partner.z1)
    target = wing.omega.rod_min_gap
    gap = lambda dp: _omega_gap(wing, partner.pct + side * dp, partner.pct, oz0, oz1)  # noqa: E731
    lo, hi = 0.0, 0.002
    while gap(hi) < target:
        lo, hi = hi, hi * 2
        if hi > 0.5:
            return None
    for _ in range(50):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if gap(mid) < target else (lo, mid)
    return partner.pct + side * hi


def _compute_omega_rod_sections(wing: WingDefinition) -> list[PhysicalRodSection]:
    """Place skin-tangent rod pairs, span by span.

    Span 0 is the master and is taken as defined. Each later rod is snapped to
    `rod_min_gap` beside the nearest rod of the previous span, on the side it was
    asked for, so the two share an omega and a tight lap. If that spot is taken
    it tries the other side, then the next inboard rod, and finally relaxes to the
    nearest free spot to where it was requested. Outboard rods also keep their
    clips off the box webs; a root rod on a web is only reported.
    """
    L_eff = wing.rod_length * (1.0 - 2.0 * wing.rod_overlap_pct)
    rod_depth = wing.rod_length * wing.rod_overlap_pct
    n_rod = math.ceil(wing.span / L_eff - 1e-9)
    if len(wing.rod_sections) != n_rod:
        raise ValueError(f"Expected exactly {n_rod} section placements in rod_sections for span "
                         f"{wing.span} and rod length {wing.rod_length}, but got {len(wing.rod_sections)}.")

    placed: list[list[_Placed]] = []
    computed: list[PhysicalRodSection] = []
    step = 0.0005

    for r in range(n_rod):
        z0 = max(0.0, r * L_eff - rod_depth)
        z1 = min(wing.span, (r + 1) * L_eff + rod_depth)
        inboard = [p for span in placed for p in span if min(z1, p.z1) > max(z0, p.z0) + 0.01]
        prev = placed[r - 1] if r > 0 else []
        mine: list[_Placed] = []
        rods: list[ComputedRod] = []

        for j, req in enumerate(wing.rod_sections[r].chord_pcts):
            others = inboard + mine
            pct, partner = None, None

            if r == 0:
                if not _omega_clear(wing, req, z0, z1, others, webs=False):
                    raise ValueError(f"root rod {j} at x/c {req:.4f} collides or does not fit; "
                                     f"the root span is the master and is not moved")
                pct = req
            elif wing.omega.snap_to_previous and prev:
                order = sorted(range(len(prev)), key=lambda i: abs(prev[i].pct - req))
                for i in order:
                    first = 1 if req >= prev[i].pct else -1
                    for side in (first, -first):
                        cand = _omega_snap(wing, prev[i], side, z0, z1)
                        if cand is not None and _omega_clear(wing, cand, z0, z1, others):
                            pct, partner = cand, i
                            break
                    if pct is not None:
                        break

            if pct is None:                       # relax: nearest free spot to the request
                for k in range(int(0.96 / step)):
                    for cand in ((req,) if k == 0 else (req + k * step, req - k * step)):
                        if _omega_clear(wing, cand, z0, z1, others):
                            pct = cand
                            break
                    if pct is not None:
                        break
                if pct is None:
                    raise ValueError(f"span {r} rod {j}: no free position on the chord")

            mine.append(_Placed(pct, z0, z1))
            (xu, yu), (_, yl) = _omega_centres(wing, pct, chord_at(z0, wing))
            rods.append(ComputedRod(abs_x=xu, abs_yu=yu, abs_yl=yl, z_cut_off=z1,
                                    pct=pct, requested_pct=req, partner=partner))

        placed.append(mine)
        computed.append(PhysicalRodSection(r=r, z_bounds_start=z0, z_bounds_end=z1, rods=rods))

    return computed


def _omega_lap_pairs(a: PhysicalRodSection, b: PhysicalRodSection) -> list[tuple[int, int]]:
    """Rod pairs handing load over across the lap from span a to span b.

    Every outboard rod pairs with its snap partner (or nearest inboard rod), and
    every inboard rod left over pairs with its nearest outboard rod, so no rod
    ends in the lap without a modifier bridging it to the next span.
    """
    if not a.rods or not b.rods:
        return []
    near = lambda rods, pct: min(range(len(rods)), key=lambda i: abs(rods[i].pct - pct))  # noqa: E731
    pairs = []
    for jb, rb in enumerate(b.rods):
        ja = rb.partner if rb.partner is not None else near(a.rods, rb.pct)
        pairs.append((ja, jb))
    taken = {ja for ja, _ in pairs}
    for ja, ra in enumerate(a.rods):
        if ja not in taken:
            pairs.append((ja, near(b.rods, ra.pct)))
    return pairs


# ──────────────────────────────────────────────────────────────
# Main layout
# ──────────────────────────────────────────────────────────────

def compute_section_layout(wing: WingDefinition) -> list[SectionInfo]:
    if wing.construction == "omega":
        return _compute_omega_section_layout(wing)
    L_eff = wing.rod_length * (1.0 - 2.0 * wing.rod_overlap_pct)
    rod_depth = wing.rod_length * wing.rod_overlap_pct
    p_h = L_eff / wing.rod_multiple
    phys_sects = _compute_physical_rod_sections(wing)
    
    sections: list[SectionInfo] = []
    z = 0.0
    rod_r = wing.rod_diameter / 2
    
    while z < wing.span - 0.01:
        z_end = min(z + p_h, wing.span)
        idx = len(sections)
        
        # Is this section the start of a new rod section?
        r_primary = idx // wing.rod_multiple
        
        holes = []
        joint_mods = []
        
        for psec in phys_sects:
            r = psec.r
            for j, rod in enumerate(psec.rods):
                # The rod exists from psec.z_bounds_start to min(psec.z_bounds_end, rod.z_cut_off)
                r_z_end = min(psec.z_bounds_end, rod.z_cut_off)
                
                # Check overlap with this print section [z, z_end]
                z_intersect_start = max(z, psec.z_bounds_start)
                z_intersect_end = min(z_end, r_z_end)
                
                if z_intersect_end > z_intersect_start + 0.01:
                    # Rod is present in this print section
                    z0 = z_intersect_start - z
                    z1 = z_intersect_end - z
                    
                    c0 = chord_at(z_intersect_start, wing)
                    c1 = chord_at(z_intersect_end, wing)
                    
                    holes.append(SectionRodHole(
                        z0=z0, z1=z1,
                        x0=rod.abs_x, yu0=rod.abs_yu, yl0=rod.abs_yl, chord0=c0,
                        x1=rod.abs_x, yu1=rod.abs_yu, yl1=rod.abs_yl, chord1=c1,
                        is_primary=(r == r_primary)
                    ))
                    
                    # Generate joint modifiers
                    # The joint modifier is placed if this rod is overlapping with another section here.
                    # We check if there's an adjacent physical section.
                    if r > 0 and z_intersect_start < r * L_eff + rod_depth:
                        # Overlap with r-1
                        pass

        # Joint mods: whenever section r and r+1 overlap, they need a joint modifier.
        # The overlap zone is [ (r+1)*L_eff - rod_depth, (r+1)*L_eff + rod_depth ]
        # Does this overlap zone fall into [z, z_end]?
        for psec in phys_sects:
            r = psec.r
            idx_next = r + 1
            if idx_next < len(phys_sects):
                next_psec = phys_sects[idx_next]
                overlap_z_start = idx_next * L_eff - rod_depth
                overlap_z_end = idx_next * L_eff + rod_depth
                
                # Check intersection with [z, z_end]
                oz0 = max(z, overlap_z_start)
                oz1 = min(z_end, overlap_z_end)
                if oz1 > oz0 + 0.01:
                    # We have overlap! Provide a joint modifier for each overlapping pair of rods
                    n_rods = min(len(psec.rods), len(next_psec.rods))
                    for j in range(n_rods):
                        r_a = psec.rods[j]
                        r_b = next_psec.rods[j]
                        
                        # Only apply up to the cutoff z!
                        eff_oz1 = min(oz1, r_a.z_cut_off, r_b.z_cut_off)
                        if eff_oz1 > oz0 + 0.01:
                            mod_z0 = oz0 - z
                            mod_z1 = eff_oz1 - z

                            # One ellipse per rod pair: from rod A's centre to
                            # rod B's centre, upper and lower deck separately.
                            joint_mods.append(SectionJointMod(
                                z0=mod_z0, z1=mod_z1,
                                xa=r_a.abs_x, ya=r_a.abs_yu,
                                xb=r_b.abs_x, yb=r_b.abs_yu
                            ))
                            joint_mods.append(SectionJointMod(
                                z0=mod_z0, z1=mod_z1,
                                xa=r_a.abs_x, ya=r_a.abs_yl,
                                xb=r_b.abs_x, yb=r_b.abs_yl
                            ))

        sec = SectionInfo(
            index=idx,
            z_start=z,
            z_end=z_end,
            female_at_root=(idx > 0),
            male_at_tip=(z_end < wing.span - 0.01),
            holes=holes,
            joint_mods=joint_mods
        )
        sections.append(sec)
        z = z_end

    return sections


def _compute_omega_section_layout(wing: WingDefinition) -> list[SectionInfo]:
    L_eff = wing.rod_length * (1.0 - 2.0 * wing.rod_overlap_pct)
    p_h = L_eff / wing.rod_multiple
    phys = _compute_physical_rod_sections(wing)

    sections: list[SectionInfo] = []
    z = 0.0
    while z < wing.span - 0.01:
        z_end = min(z + p_h, wing.span)
        idx = len(sections)
        r_primary = idx // wing.rod_multiple
        holes: list[SectionRodHole] = []
        joint_mods: list[SectionJointMod] = []

        for psec in phys:
            za, zb = max(z, psec.z_bounds_start), min(z_end, psec.z_bounds_end)
            if zb <= za + 0.01:
                continue
            c0, c1 = chord_at(za, wing), chord_at(zb, wing)
            for rod in psec.rods:
                (xu0, yu0), (xl0, yl0) = _omega_centres(wing, rod.pct, c0)
                (xu1, yu1), (xl1, yl1) = _omega_centres(wing, rod.pct, c1)
                holes.append(SectionRodHole(
                    z0=za - z, z1=zb - z,
                    x0=xu0, yu0=yu0, yl0=yl0, chord0=c0,
                    x1=xu1, yu1=yu1, yl1=yl1, chord1=c1,
                    is_primary=(psec.r == r_primary),
                    xl0=xl0, xl1=xl1, pct=rod.pct))

        for a, b in zip(phys, phys[1:]):
            za = max(z, b.z_bounds_start, a.z_bounds_start)
            zb = min(z_end, a.z_bounds_end, b.z_bounds_end)
            if zb <= za + 0.01:
                continue
            c0, c1 = chord_at(za, wing), chord_at(zb, wing)
            for ja, jb in _omega_lap_pairs(a, b):
                pa, pb = a.rods[ja].pct, b.rods[jb].pct
                for deck in (0, 1):                    # 0 = upper, 1 = lower
                    A0, A1 = _omega_centres(wing, pa, c0)[deck], _omega_centres(wing, pa, c1)[deck]
                    B0, B1 = _omega_centres(wing, pb, c0)[deck], _omega_centres(wing, pb, c1)[deck]
                    joint_mods.append(SectionJointMod(
                        z0=za - z, z1=zb - z,
                        xa=A0[0], ya=A0[1], xb=B0[0], yb=B0[1],
                        xa1=A1[0], ya1=A1[1], xb1=B1[0], yb1=B1[1]))

        sections.append(SectionInfo(
            index=idx, z_start=z, z_end=z_end,
            female_at_root=(idx > 0),
            male_at_tip=(z_end < wing.span - 0.01),
            holes=holes, joint_mods=joint_mods))
        z = z_end

    return sections


def print_omega_placement(wing: WingDefinition) -> None:
    """Requested vs placed rods, what each was snapped to, and web clearances."""
    om = wing.omega
    phys = _compute_physical_rod_sections(wing)
    print(f"Omega construction: skin {om.skin_wall:.2f} mm (rod bears at "
          f"{omega_skin_offset(wing):.2f}), clip {om.omega_wall:.2f} mm, "
          f"webs {om.box_wall:.2f} mm at x/c {om.front_web_pct:.2f} / {om.rear_web_pct:.2f}, "
          f"min rod gap {om.rod_min_gap:.2f} mm")
    for psec in phys:
        print(f"  span {psec.r}  z {psec.z_bounds_start:5.1f}->{psec.z_bounds_end:5.1f}")
        prev = phys[psec.r - 1] if psec.r > 0 else None
        for j, rod in enumerate(psec.rods):
            moved = rod.pct - rod.requested_pct
            note = ""
            if rod.partner is not None:
                gap = _omega_gap(wing, rod.pct, prev.rods[rod.partner].pct,
                                 psec.z_bounds_start, prev.z_bounds_end)
                note = f"snapped to span {psec.r - 1} rod {rod.partner}, gap {gap:.2f} mm"
            elif psec.r > 0 and abs(moved) > 1e-9:
                note = "relaxed (no free snap spot)" if om.snap_to_previous else "moved clear"
            elif psec.r > 0:
                note = "as requested"
            webs = _omega_web_clearance(wing, rod.pct, psec.z_bounds_start, psec.z_bounds_end)
            for name, clear in webs.items():
                if clear < 0:
                    note += f"  !! clip crosses {name} web ({clear:+.2f} mm)"
            print(f"    rod {j}: x/c {rod.requested_pct:.4f} -> {rod.pct:.4f} "
                  f"({moved * chord_at(psec.z_bounds_start, wing):+6.2f} mm)  {note}")


def print_layout(wing: WingDefinition, sections: list[SectionInfo]) -> None:
    L_eff = wing.rod_length * (1.0 - 2.0 * wing.rod_overlap_pct)
    n_rod_float = wing.span / L_eff
    print(f"\n{'='*60}")
    print(f"Wing: NACA {wing.naca}, span={wing.span}mm, "
          f"chord {wing.root_chord}→{wing.tip_chord}mm")
    print(f"Total sections: {len(sections)}")
    print(f"{'─'*60}")
    for s in sections:
        jnt = ("←female" if s.female_at_root else "  root ") + \
              (" male→" if s.male_at_tip else "  tip  ")
        print(f"  S{s.index:02d}: z={s.z_start:6.1f}→{s.z_end:6.1f}mm  "
              f"chord={chord_at(s.z_start, wing):5.1f}→{chord_at(s.z_end, wing):5.1f}  "
              f"{jnt}  Holes={len(s.holes)} Mods={len(s.joint_mods)}")
    if wing.construction == "omega":
        print(f"{'─'*60}")
        print_omega_placement(wing)
    print(f"{'='*60}\n")
