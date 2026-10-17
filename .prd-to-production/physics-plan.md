# MuJoCo physics integration map — proposed, not implemented

17 October 2026. Supplements brief v2 without recording approval or authorizing a build. Goal: make the two-minute Scene2Real demo show perception-driven, dynamically executed predefined aiming with measured hits. Keep synthetic input and the working Cosmos/JSON interface.

## Evidence from both repositories

Scene2Real already has MuJoCo dynamics: `scene2real/sim.py:simulate` runs `mj_step` at the authored 0.002 s timestep, drives position actuators, measures angular error and contacts, and exports 30 fps world-geom poses. Three.js replays those poses. This is not currently a purely kinematic browser animation.

The current model is a four-joint primitive approximation, with body gravity compensation, uniform kp=600, high joint damping and no explicit actuator force limits. Spray turns on at two simulated seconds regardless of hits; collision metrics broadly ignore contacts inside the arm/tool chain. Mesh geometry is not supported by the trajectory exporter. Replacing the model therefore needs both simulation and renderer work.

GhostGUI inspected at commit `769b65b5bdc55c1364c5edb2d27b7119ba5b7953`:

- `core/models/adapter.py`: compiled-model adapter, joint metadata and logical frames.
- `core/models/model.py`: weighted/hierarchical Jacobian IK and qpos timeline.
- `core/ik/collision.py`: support-contact versus blocking-contact policy.
- `core/robotics/contracts.py`: model-sized finite qpos and trajectory validation.
- `docs/motion_math.md`: interpolation, SLERP, primary Cartesian/secondary posture tasks.
- `docs/data_formats.md`: model-dependent qpos ordering, radians/metres, quaternion conventions and named G1 export mapping.
- `scripts/view_g1_mujoco.py:apply_current_row`: playback assigns qpos and calls mj_forward. That path visualizes a reference; it does not demonstrate dynamic tracking. The optional C++ backend is also not a substitute for a dynamics controller.

Reuse GhostGUI as the pose-authoring and reference-validation tool. Initially exchange exported, model-matched pose data rather than importing the Qt application or its full dependency tree. Any adapted code keeps its MIT notice; robot assets retain their separate BSD-3-Clause notice.

## Authority and clocks

One Python simulation owner holds MjModel/MjData per active session. The server owns physics state, approved commands, scene revision and suppression intensity. Browser camera rendering and user scene-edit commands reference exact server state IDs. Never run a second independent browser physics world.

Proposed loop rates, to benchmark rather than promise:

- Physics: retain 500 Hz fixed integration (2 ms).
- Controller: initially run at each physics step; decimation can follow measurement.
- State publication: 30 Hz, with simulation time and sequence number.
- Three.js display: interpolate consecutive actual body poses at display refresh.
- Cosmos: asynchronous snapshot requests with one current request in flight; never block physics on inference.

For slow inference the robot holds a controlled posture with spray off. Control watchdog expiry, invalid results or disconnect revoke spray permission. A controlled stop still applies stabilizing actuator control; zeroing all torque can drop an arm or a future floating-base robot.

## Phase 1 — canonical G1 and tool physics

Use the supplied pinned Menagerie G1 MJCF as the canonical mechanical model: body frames, joint axes/ranges, inertias, masses, damping, armature and actuator definitions. Preserve the original source and describe all modifications in an overlay/manifest. The linked robot is G1, not R1.

Create an explicitly fixed-base demo variant, preserving articulated limb dynamics. Add a rigid wrist tool body with authored mass/inertia and a nozzle site whose local forward axis is documented. Add a head/chest robot camera with explicit extrinsics and FOV. Derive browser geometry and link mapping from this same source, accounting for mesh scale and local transforms. Do not derive physics inertias from a simplified display GLB.

Use detailed visual meshes, source collision geometry or explicitly documented simplified collision proxies. Add mesh asset references to the existing trajectory format without removing legacy primitive support. Compare home and three target poses between MuJoCo and browser rendering, including nozzle/camera orientation. Convert wxyz to xyzw only at the Three.js boundary; retain metres, radians and a shared Z-up convention.

Gate: model compiles; named joint/actuator mapping resolves; tool affects mechanics; joint and camera transforms match; license provenance is present.

## Phase 2 — dynamically execute authored motions

Author rest/left/center/right in GhostGUI using the exact matching G1 variant or a name-based adapter to it. Validate endpoints and sampled intermediate paths. Reject incompatible qpos widths, joint names, nonfinite values and source-model hashes. Floating-base qpos exports cannot be copied by raw index into a fixed-base model.

Convert the three motions into named joint references. Use a bounded transition (e.g. quintic time scaling between checked scalar-joint endpoints); stretch timing until configured velocity/acceleration limits pass. Recheck intermediate collisions. These are predefined authored motions, even if IK helped author them.

Feed references into finite-force actuators or an explicit PD controller:

`tau = clip(Kp*(q_ref-q) + Kd*(qd_ref-qd) + tau_ff, torque_limits)`

Map qpos and velocity/force DOFs separately by compiled names. Choose joint-specific gains and limits from verified model/motor data, documenting estimates. Avoid layering an external PD loop on top of an already equivalent internal position/velocity servo. Replace blanket body gravcomp with a documented controller strategy; record any model-based gravity feedforward.

Never assign the reference directly to live qpos during execution. Reserve qpos writes for initialization/reset and a separate offline preview state. Keep the existing IK solver out of live fixed-preset execution.

Gate: plot desired versus actual joint angles, tracking error and actuator saturation; an obstacle changes actual motion and prevents the nozzle reaching the commanded orientation; a heavier tool changes effort/tracking without teleporting.

## Phase 3 — hit-dependent suppression in the physics world

Calculate nozzle origin/heading from the actual MuJoCo site transform at the measured simulation state. Refresh the required kinematics before sampling ray/camera/body transforms. Query nearest intersections using mj_ray, including static environment blockers. Filter visual-only geoms so duplicate visual/collision shapes do not create false hits; exclude the nozzle housing deliberately, not the entire robot.

Represent each fire with a non-contact hit volume and intensity. Compare ray intersections with fire volumes against the nearest physical blocker; require a positive hit within configured range. A target behind a wall, wrong aim or no spray contributes zero exposure. A non-contact fire marker need not participate in solid-body collision response.

Initial rule: `I_next = max(0, I - k * hit * spray_enabled * dt)`, with I in [0,1] and k an explicitly authored demo coefficient. Single ray first; a later sampled cone can use the fraction of unobstructed rays hitting. This is exposure-based simplified suppression, not fluid or thermal physics. Synchronize the visible spray endpoint and effects with the recorded blocking intersection.

Refine contact reporting to allow designed wrist-tool adjacency and foot-floor support while retaining actual arm self-collisions and environment collisions. Record contact force/impulse where useful; do not equate every support contact with failure.

Gate: correct aim lowers intensity, wrong aim and blocking wall do not; hitting while actuators are deflected follows actual rather than commanded pose. Keep existing aiming success semantics and add separate suppression outcome fields.

## Phase 4 — live perception loop and compatible JSON

Keep existing REST run routes, observation fields, saved trajectories and replay. Add a session layer and state stream only where needed for interactive fire movement. Preserve the existing Cosmos request/validation adapter, adding explicit no-fire/uncertain decision handling without weakening legacy callers.

The browser renders robot-camera pixels from an identified server snapshot; observer view is separate. Save image bytes/hash, camera transform/intrinsics, snapshot ID, physics sequence/time and scene revision. Infer only from pixels and the existing prompt context: do not send fire coordinates, scenario names or hidden target labels to Cosmos.

Decisions return with snapshot ID, parsed/raw evidence and wall-clock latency. Map validated image-relative decisions to authored presets; the simulator may know fire coordinates for evaluation, but the selector must not consult them. Define left/right in the robot-camera frame. Unknown depth/cause alone must not invalidate otherwise valid existing observations.

Scene edits/reset invalidate pending and active decisions immediately. Camera movement, robot displacement or other physical scene changes require bounded pose/age freshness checks; do not simply invalidate on every simulation step. Retain snapshot identity throughout planned motion and invalidate material perception changes. Use a finite command lease and periodic re-observation; expiry turns spray off. Exact lease/freshness thresholds must be set from measured Cosmos latency, and changed-scene cases may require reanalysis rather than unsafe long leases.

Add optional fields for physics state, desired/actual joints, contact events, nozzle ray, hit object/distance, fire intensity, decision validity and frame references. Do not rename existing fields or silently redefine legacy success. Publish authoritative outcomes; browser interpolation never determines suppression.

Gate: move fire while Cosmos is pending and prove the late answer cannot spray; no-fire, uncertainty, malformed output, timeout and disconnect revoke permission. A valid response never blocks the physics worker.

## Phase 5 — evidence and later whole-body work

Run left/center/right, no-fire, obscured and deliberate wrong-aim cases, plus obstacle blocking and stale inference. Record actual inference and failures; fixtures can test gating but cannot count as live Cosmos evidence. Compare against the current baseline with identical target geometry.

Persist model/asset hashes, engine version, solver/timestep/controller settings, initial integration state, references, applied controls, scene edits, actual inference responses and application times. Save state checkpoints and the suppression state for replay. Record tracking RMS/peak, torque saturation duration, contacts, nozzle angular error, hit exposure and intensity trace. Record robot-camera input sequence and an observer video tied to the same simulation timestamps. Replays use saved decisions rather than calling the nondeterministic model again; promise measured numerical tolerance on a pinned configuration, not universal bitwise identity.

After the demo: floating-base G1, realistic foot friction/contact, balance control and perturbation tests. GhostGUI planted-foot IK constrains a reference pose but is not a dynamic balance controller. Evaluate whole-body control or a compatible G1 standing policy before removing support. Walking, learned policy training and fluid simulation remain separate scope decisions.

## Parallel work and what to adopt

- [Menagerie pinned G1](https://raw.githubusercontent.com/google-deepmind/mujoco_menagerie/62ab00f2bc44f6f20c1c9b7a13f3fb1dd41a4e35/unitree_g1/README.md): geometry/mechanical reference; README warns position actuators need tuning and describes lower-gain MJX changes. Do not assume imported assets are already a calibrated controller.
- [GhostGUI](https://github.com/yx-lim/ghostgui/tree/769b65b5bdc55c1364c5edb2d27b7119ba5b7953): authored references, IK, collision validation, explicit state ownership and model-aware data contracts.
- [Mink](https://github.com/kevinzakka/mink): MuJoCo differential IK with position/velocity limits and collision avoidance; useful for a later constrained aiming controller. It supplies references, not a guarantee of torque feasibility or balance.
- [Unitree MuJoCo](https://github.com/unitreerobotics/unitree_mujoco): SDK-compatible low-level control/state interface; useful for later joint ordering, motor control and sim-to-real interface work. No DDS dependency is required for this browser demo.
- [MuJoCo Playground](https://github.com/google-deepmind/mujoco_playground): G1 learning/sim-to-real and accelerated training route for later balance policies and randomized evaluation. CPU MuJoCo is the initial single-scene runtime; profile before adding MJX/Warp infrastructure.
- [MuJoCo modeling](https://mujoco.readthedocs.io/en/stable/modeling.html) and [ray API](https://mujoco.readthedocs.io/en/stable/APIreference/APIfunctions.html#mj-ray): authoritative modeling, coordinate and ray-query behavior. Implementation must check the installed engine version rather than assume HEAD signatures.

## Smallest useful delivery sequence

1. Fixed-base G1 + dynamic preset tracking + collision/hit-dependent outcomes, retaining recorded trajectory transport.
2. Authoritative live session, state streaming and robot-camera inference with staleness guards.
3. Full evidence run and recording, then optional floating-base balance work after the hackathon.

Main files: `scene2real/scene.py` (canonical assets/tool/collision scene), `sim.py` (controller, physics, rays and metrics), `app.py`/`pipeline.py` (session/commands), `cosmos.py` (camera decision semantics), `records.py` (evidence), `static/app.js` (mesh/state renderer and camera capture). Introduce small dedicated controller/session helpers only if they keep these changes isolated; avoid a general simulation-framework rewrite.
