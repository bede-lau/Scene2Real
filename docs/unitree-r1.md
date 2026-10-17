# Unitree R1 reference for the demo

The demo uses an **authored, simplified robot inspired by the standard Unitree R1**. The physical robot's specifications are context for its visual proportions, not a claim that our scripted simulation imports the complete robot, models its dynamics, or establishes a real robot's firefighting capabilities.

## Primary sources and attribution

- Unitree's [R1 product specifications](https://www.unitree.com/mobile/R1/) list the standard R1 at 1230 × 357 × 190 mm standing, approximately 29 kg with battery, 26 joint degrees of freedom (6 per leg, 5 per arm, 2 waist, 2 head), 600 mm combined thigh and calf, 420 mm combined upper arm and forearm, and a binocular camera. Unitree notes specifications and appearance can vary by configuration.
- Unitree Robotics' official [R1 URDF](https://github.com/unitreerobotics/unitree_ros/blob/5994d4faef0a9cadd3287f8de0199a67eeb2a259/robots/r1_description/R1.urdf) in `unitree_ros` (revision `5994d4faef0a9cadd3287f8de0199a67eeb2a259`) describes the standard R1's link/joint layout and white, light grey and dark grey materials. Copyright © 2016–2022 HangZhou YuShu TECHNOLOGY CO., LTD. (Unitree Robotics), [BSD 3-Clause](../third_party/unitree_r1/LICENSE).
- The [reference URDF](../third_party/unitree_r1/R1.urdf) is included for inspection. Its 42 distinct STL mesh references are **not included**, so the file cannot be loaded on its own. The [upstream mesh directory](https://github.com/unitreerobotics/unitree_ros/tree/5994d4faef0a9cadd3287f8de0199a67eeb2a259/robots/r1_description/meshes) and license are available from the same repository. No product photograph is redistributed here.

## Intended approximation

Use a compact biped with two legs and two arms, a rounded head with binocular sensor styling, a compact torso and segmented limbs with visible joint transitions. Use the official material palette as a starting point. Overall height, width and depth are published values; limb thickness, facial details and the precise shape of simplified primitives are artistic approximations. Combined limb lengths must not be mistaken for individually measured thigh, calf, upper arm or forearm dimensions. A hypothetical water nozzle and charging station are demo additions.

The scripted proxy's actual joints and action schema are defined by the mobile simulator, not the 26-joint URDF. Walking is an animation driven by the proxy's controller; spray exposure is a demo metric, not validated fire physics. Preserve confirmed incident targets, provenance and uncertainty. No physical fire suppression performance or real robot readiness is implied.

`scene2real.robot_profile.r1_system_prompt()` returns factual context and these constraints for the planner; the caller must append it to the existing trusted system instructions while retaining their response schema and incident validation.

The vendored URDF uses LF line endings; its upstream CRLF line endings were normalized without changing the robot description.
