"""Verified Unitree R1 reference and boundaries for the authored demo robot.

The official URDF and license are in third_party/unitree_r1. This profile does
not import the URDF into the simulator or grant the proxy its physical joints.
"""
from __future__ import annotations

ROBOT_PROFILE = {
    "name": "Unitree R1",
    "variant": "standard R1 (not R1 AIR or R1 EDU)",
    "reference_kind": "authored, reduced-control visual approximation",
    "standing_dimensions_m": [1.230, 0.357, 0.190],  # height, width, depth
    "mass_with_battery_kg_approx": 29,
    "joint_dof_total": 26,
    "joint_dof_per_leg": 6,
    "joint_dof_per_arm": 5,
    "joint_dof_waist": 2,
    "joint_dof_head": 2,
    "combined_thigh_calf_length_m": 0.600,
    "combined_upper_arm_forearm_length_m": 0.420,
    "camera": "binocular",
    "leg_joints": ("hip pitch", "hip roll", "hip yaw", "knee", "ankle pitch", "ankle roll"),
    "arm_joints": ("shoulder pitch", "shoulder roll", "shoulder yaw", "elbow", "wrist roll"),
    "waist_joints": ("roll", "yaw"),
    "head_joints": ("pitch", "yaw"),
    "urdf_material_rgba": {
        "dark": (0.4, 0.4, 0.4, 1.0),
        "light_grey": (0.7, 0.7, 0.7, 1.0),
        "white": (0.95, 0.95, 0.95, 1.0),
    },
    "specification_url": "https://www.unitree.com/mobile/R1/",
    "reference_url": "https://github.com/unitreerobotics/unitree_ros/blob/5994d4faef0a9cadd3287f8de0199a67eeb2a259/robots/r1_description/R1.urdf",
    "license": "BSD-3-Clause; see third_party/unitree_r1/LICENSE",
}


def r1_system_prompt() -> str:
    """Return a factual design context to append to the planner's system prompt.

    This is deliberately additive: the calling planner owns the response schema,
    supported actions and all validated incident and target data.
    """
    return """Robot reference for this simulation: represent an authored, simplified
humanoid visually inspired by the standard Unitree R1. The manufacturer's
published standing dimensions are 1.230 m tall, 0.357 m wide and 0.190 m deep;
approximately 29 kg including battery. It has 26 joint degrees of freedom: each
leg has hip pitch/roll/yaw, knee and ankle pitch/roll (6 each); each arm has
shoulder pitch/roll/yaw, elbow and wrist roll (5 each); waist roll/yaw and head
pitch/yaw each add 2. The combined thigh and calf length is 0.600 m and the
combined upper and lower arm length is 0.420 m. The standard model has a
binocular camera. Unitree's reference URDF defines white, light grey and dark
grey materials. Use those facts for a compact, bipedal humanoid visual style.
Reference: Unitree's R1.urdf, BSD-3-Clause; provenance and license are in
third_party/unitree_r1. These are reference facts, not simulation measurements.

The scene is a reduced-control scripted proxy, not a full R1 physics model:
its actual controllable joints, actions, scene templates and response schema are
only those provided elsewhere in this system prompt. Do not assert that all 26
joints are simulated or request unsupported joints, motions or capabilities.
The charging station, walking animation, water nozzle and fire suppression are
authored demo elements; do not claim they are verified real R1 equipment,
autonomous capabilities or a safe real-world firefighting procedure. Preserve
the operator-confirmed fire IDs, targets, locations, source observations and
uncertainties exactly as provided. Image coordinates are not measured 3D
positions. Do not invent measurements, physical guarantees or observations.
Output only the planner's required structured response; never output executable
code or arbitrary simulation XML."""
