# Scene2Real — compact PRD v2

Upgrade the existing Three.js/Cosmos simulation for the two-minute demo. Describe it as a **perception-driven animated prototype with simplified suppression physics**; motion is predefined, never a trained robot policy.

**P-workbench**, `/`: one responsive workbench; observer and robot-camera views; scenario controls, Cosmos evidence, aiming/spray state, results and recording. No additional routes or tabs.

- **R-input:** Use the generated synthetic scene/video by default; no video upload required. Only robot-camera imagery reaches Cosmos; exclude observer images, UI overlays and hidden scene truth. Label synthetic inputs.
- **R-robot:** Use linked Menagerie `unitree_g1` assets at commit `62ab00f2bc44f6f20c1c9b7a13f3fb1dd41a4e35`. Convert to browser-compatible articulated geometry, preserving scale, hierarchy, axes and joint limits. Attach the nozzle to the wrist; retain license and attribution. The link is G1 despite the request saying R1; use G1 naming.
- **R-scene:** Add grounded floor, lighting, shadows, three target positions and movable fire. Aim for an NVIDIA Isaac Sim-style industrial environment rendered in Three.js. Provide observer and robot cameras.
- **R-action:** Map existing validated decisions to left/center/right predefined arm poses. Animate smooth transitions within joint limits. Clearly label predefined motion. Deliberate wrong-aim testing must be visibly identified as an override.
- **R-hits:** Cast a ray from the nozzle’s current world position along its current world heading. Reduce fire intensity over elapsed time only on an unobstructed spray hit. An earlier obstacle intersection blocks suppression; misses and wrong aim leave intensity unchanged. Log actual hits/misses independently of model claims.
- **R-safety:** Stop spraying on no fire, uncertainty, invalid output or inference failure. Associate each response with its camera snapshot; scene changes invalidate pending and active decisions. Discard stale responses. New imagery and valid decisions are required before spraying resumes.
- **R-contract:** Keep the working Cosmos endpoint, server-side credentials, Weave tracing, validated observation JSON and existing run interface compatible. Add snapshot/decision/result metadata without deleting existing fields. Do not replace actual inference with synthetic decisions.
- **R-evaluation:** Demonstrate left, center, right, no fire, obscured view and deliberate wrong aim. Save robot-camera inputs, actual Cosmos responses/validated decisions, response times, hit/miss results and a playable recording linked to runs. Verify failure stops spray, stale decisions cannot actuate, obstacles block rays, and joints remain within limits. Keep README Inputs/Outputs/Evaluation current; distinguish observed results from blocked or untested cases.

**Assumptions:** Fixed-base robot; presets cover three authored target positions. Movable fires outside valid preset coverage may remain unsuppressed. Synthetic video is rendered scene imagery, with no required external video generation service. Visibility uncertainty must be explicit and validated; ordinary unknown depth/cause alone is not a reason to reject every existing Cosmos response.

**Exclusions:** Isaac Sim integration, trained policies, walking/grasping, physical robot control, reconstructed metric scenes, fluid dynamics, realistic combustion and real-world suppression claims.
