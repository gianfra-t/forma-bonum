
from wing_assembler import WingDefinition, RodSection, OmegaSettings


SPAN = 290.0
CHORD = 50.0

wing = WingDefinition(
    span=SPAN,
    root_chord=CHORD,
    tip_chord=CHORD,
    naca="rect50",                     # 50 x 25 mm rectangle
    rod_length=SPAN,                   # one rod span, the full coupon
    rod_multiple=1,
    rod_overlap_pct=0.0,               # no lap
    rod_diameter=2.2,                  # omega tube orifice
    skin_distance=2.0,                 # unused by omega
    joint_length=15.0,                 # unused: single section, no joints
    joint_thickness=0.45,              # still sets how deep the rod bears (max with the skin)
    clearance=0.0,
    epoxy_gap=0.3,
    axial_gap=0.3,
    rod_sections=[
        RodSection(chord_pcts=[0.25, 0.75]),   # 2 upper + 2 lower rods
    ],
    construction="omega",
    omega=OmegaSettings(
        line_width=0.42,
        skin_lines=1,
        omega_lines=1,
        omega_clearance=0.0,
        omega_neck_width=None,
        omega_foot_length=1.0,
        rod_min_gap=0.5,
        box=False,                     # no webs, no cell modifiers
    ),
)
