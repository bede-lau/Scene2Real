# Scene2Real — compact PRD v1

**Goal:** Help robotics/safety teams turn warehouse-fire footage into repeatable robot rehearsals: video → Cosmos evidence → structured scenario → instruction → simulation → measured outcome. Hackathon scope: one complete loop in ~7 hours.

**Scope:** Multiple warehouse-fire clips; one active clip and one confirmed response target per MVP run. Retain all detected fires, act on one. Second-clip adaptation is v2.

**Screen:** P-workbench, `/`, one responsive page, no tabs.

## Requirements

- **R-input:** Accept an authorised warehouse-fire MP4 or preloaded clip; retain source reference. Demo one pinned clip. No clip browser/comparison. Show validation, progress and retryable errors.
- **R-analysis:** Use real Cosmos reasoning, preferably event Cosmos3-Reason/CoreWeave. Display its response and validated observations: source IDs, evidence timestamps, normalised image regions, unknowns. Unknown cause/scale/depth stays null. Available YOLO detections supplement objects; fire detection is not assumed.
- **R-target:** User confirms one fire source and its authored warehouse zone. Unsupported, ambiguous or unmappable targets require review; execution stays blocked. Image observations and template-assumed metric positions remain distinct.
- **R-scene:** Generate a parameterised MuJoCo warehouse: racks, pallets, collision geometry, fire markers, fixed-base humanoid and attached extinguisher. Record placement provenance. Use authored geometry; no precise reconstruction claim.
- **R-action:** Generate a short instruction plus validated skill/target plan using W&B hosted inference; if unavailable, label and use a deterministic instruction/plan fallback. Execute only `aim_spray_demo` against the confirmed source. Reject invalid plans, unsupported skills and unreachable targets. Use scripted joint targets/keyframes with physics; fire/spray are visual effects. Support Run, Reset and replay of the same scene.
- **R-results:** Measure nozzle/target angular error, unintended robot/environment collisions and simulated duration. Aiming success: error ≤5° for two continuous simulated seconds, zero unintended collisions; exclude attachment contacts. Never infer success from an LLM. Before delivery, complete one real analysis→simulation run, repeat it three times successfully, and verify invalid analysis/plan blocks execution and service failure exposes Retry. Log stage latency; no real-time promise.
- **R-records:** Persist run-linked source, observations, assumptions, confirmed target, instruction/skill, scene settings, model/prompt IDs, timings and outcome. Use configured VAST archive access and W&B Weave traces/evaluation; report skipped telemetry without blocking simulation. Secrets stay server-side. Label genuine cached inference; mock output cannot satisfy real-analysis acceptance.
- **R-workbench:** P-workbench sections: video; Cosmos text/JSON; source/zone confirmation; instruction; simulation; metrics. Controls: Analyse → Generate scene → Run; Reset after scene creation. Enable controls only at valid stages. Stack sections on mobile; support keyboard operation.

## Contract

Run object: `run_id, clip_ref, model_id, observations, confirmed_target, scene, instruction, skill, metrics`. Observations contain `fire_sources[{id,timestamps_s,bbox_normalized}], unknowns`; unobserved fields are null. Bounding boxes: `[x_min,y_min,x_max,y_max]`, range 0–1, top-left origin. Scene contains template ID, source/zone mapping and placement provenance. Skill contains supported name/target ID. Metrics contain measured angle, duration, collisions and success.

## Constraints

Python backend + MuJoCo + minimal web UI. Prefer supplied event adapters; verify actual endpoints/credentials. Custom fire-video ingestion is unconfirmed: resolve first; otherwise use a labelled local upload/archive adapter with real Cosmos analysis, preserving warehouse-fire scope.

**MVP example:** clip shows burning packaging beside the right pallet rack → Cosmos evidence → confirm F1/right-rack zone → generated warehouse → “Aim the attached extinguisher at F1” → humanoid aims/sprays → measured result.

**Excluded:** walking, grasping/nozzle manipulation, policy training, physical-robot control, fire/fluid/suppression physics, real-world suppression or sim-to-real claims, authentication, production hardening. V2: second clip adaptation, multiple-source responses.
