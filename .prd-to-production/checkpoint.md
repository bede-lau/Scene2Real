# Scene2Real v2 checkpoint

User approved v2 + fast-track, then explicitly requested detailed Unitree R1 reference and realistic API CCTV inputs. Native workbench and existing branding retained; separate mockup approval waived by the user.

Implemented 1–3-view Cosmos intake, raw/rich per-view evidence and uncertainty, operator grouping/exclusion and authored positions, actual Astra instruction/settings, R1-informed reduced-control robot, charging-station departure/scripted walk/water exposure, deterministic metrics, MP4 export and 1x/2x/4x playback.

Final local checks: 83 Python tests; focused Node evidence/provenance/verdict checks; real uncached providers for both new CCTV sets; eight successful mechanical simulation runs total; responsive browser replay, persistence and evidence checks. Independent API Astra findings repaired and retested. See qa/results.md and qa/matrix.md for exact scope/evidence.

Known limitation: Cosmos sometimes overcounts and misplaces boxes; independent image edits do not prove cross-camera identity. Operator groups are assumptions, and complete physical-fire coverage is unverified. Do not promote mechanical PASS to visual/reconstruction accuracy. No VM deployment or full R1/fire physics claim.

Release content includes the six registered CCTV clips, generation prompts, R1 reference/license and compact QA evidence. Credentials remain external; verification is local, with no VM deployment claim.

# Checkpoint — live simulation upgrade

- Phase: implementation and local verification. User explicitly instructed “update and launch the new localhost” after reviewing the brief and physics plan; proceed with implementation as requested. No fabricated mockup approval was recorded.
- Additional user decision: “Launch locally with Cosmos disabled for now.” Live inference is therefore disabled by default and no external Cosmos acceptance is claimed. Automatic spray remains inhibited without actual current inference.
- Runtime: ./run_local.sh at http://localhost:8090. Video workbench /; live G1 rehearsal /live.html (merged with main). Existing /api/runs and Cosmos observation contract preserved; additive /api/live routes.
- Robot: pinned Menagerie G1,29 original articulated joints/inertias, explicit fixed-base variant, finite-force actuators, .55kg wrist tool;35 converted meshes with original BSD notices/source hashes. It is G1 despite original request saying R1.
- Implemented: warehouse floor/racks/burners/lighting/shadows, movable fire/obstacle, observer and robot cameras, quintic predefined motion references executed in MuJoCo, actual nozzle-ray hit suppression, failure/staleness guards, camera-only snapshot evidence, recording and JSON download.
- Design direction and component map: design/spec.md and component-map.md. No image-generation assets or synthetic decision responses used for production behavior. Actual browser render is the scene evidence.
- Verification: full Python suite70 passed;38 browser checks passed on desktop/mobile; final restart smoke passed. Exact final outcomes recorded in qa/results.md.
- Known local scope: fixed base, authored finite servo settings, scripted motions rather than trained policy; exposure/ray suppression rather than fluid/combustion simulation. Live inference/real Cosmos responses intentionally unrun.
- Modified paths: scene2real/{live.py,live_model.py,app.py}; static/{index.html,live-app.js,live.css,legacy.html,vendor,assets}; assets/unitree_g1; scripts/fetch_g1_assets.py; tests/test_live*.py; README and workflow artifacts.
- Complete for current local-preview scope. Final server restarted and left running at localhost:8090. Recording, screenshots,6 camera inputs and JSON evidence copied to output/live-demo/. Live Cosmos acceptance deferred by explicit user choice; no real inference or live authorized suppression claimed.
