# Local verification — 17 October 2026

Environment: Python3.12/.venv, MuJoCo3.16.0; FastAPI at http://localhost:8090.
Browser plugin absent; existing Playwright1.62.1 with installed Google Chrome used.
Native sandbox Chrome aborts, so authorized escalated headless Chrome was used.
Desktop1440x1000; mobile390x844. No browser package added.

## Automated engine/API regressions

- .venv/bin/python -m pytest -q: **70 passed** (17.82s), exit0.
- node --check static/live-app.js: exit0.
- git diff --check: exit0.
- Two existing FastAPI on_event deprecation warnings; no functional failures.
- Source G1 joint axes/ranges/inertias and compiled mesh conversion verified.
- Real engine target-ray tests left/center/right; blocker and wrong aim maintain intensity.
- Finite forces, actual qpos limits, quintic reference speed bounds, contact response.
- Inference safety tests use explicit unit-test fixtures, not live Cosmos acceptance.
- Archived image/video download after cleared runtime sessions tested.

## Browser journeys

**38/38 checks passed** (36 main UI checks plus wrong-aim/video-decode verification) in /private/tmp/scene2real-live-qa/qa-results.json.
No console errors/warnings or failed requests.

Verified: meaningful primary content, two actual canvases, no upload step, inference disabled,
three physical target placements and distinct actual articulated arm motion, no manual spray
authorization, blocker toggle matches physical state, lateral fire movement, no-fire0 intensity,
obscured/wrong cases, pause/resume, reset, camera views/home, real recording and saved bytes,
six actual robot-camera inputs, JSON evidence export, desktop/mobile, no horizontal overflow,
legacy video workbench. Wrong-aim recording additionally measured22.595deg with centered fire,
manual left pose, intensity1 and spray off.

Camera framing defect from first render fixed and recaptured. Blocker checkbox field mismatch
fixed server-side and retested. Actual desktop/mobile screenshots inspected for scene framing,
font readability, control hierarchy, palette/contrast, canvas sizing and overflow. No approved
mockup image baseline exists; direct implementation was requested by the user, so screenshots
are observed implementation evidence, not retrospectively approved designs.

## Recording and evidence

- /private/tmp/scene2real-live-qa/six-scenarios.mp4: H264,1280x800,43.93s,1,278 decoded frames; full ffmpeg decode exit0.
- /private/tmp/scene2real-live-qa/six-scenarios-seekable.webm: VP9,1280x800,43.906s, remuxed seekable copy.
- Original WebM archived under runs/live_5b7d870de2d5/recording_7ed11e96.webm.
- /private/tmp/scene2real-live-qa/camera-{left,center,right,none,obscured,wrong}.jpg.
- /private/tmp/scene2real-live-qa/run-evidence.json and recording-results.json.
- Final screenshots desktop-final.png, mobile-full.png, mobile-viewport.png in the same folder.

Recording labels distinguish predefined fixed-base motion, no trained policy, synthetic robot
camera, disabled Cosmos and spray off. **Zero actual inferences**: user chose to disable Cosmos.
This is not evidence of a working external perception loop or live perception-driven suppression.
Those real-provider acceptance cases remain deferred until explicitly enabled/configured.

Final server restart smoke is recorded separately after loading final persistence guards.

Final restart smoke PASS: fresh page ready, configured model available, Cosmos disabled, actual left joint motion, Stop spray off; restored center/center/resumed/no blocker. Historical recording HTTP200 (8,008,207 bytes), archived evidence live=false, inferences=[]; no browser errors. See output/live-demo/final-smoke.json. Final evidence contains600 events and zero inferences. Deliverable copies live under output/live-demo/ (gitignored, deliberately retained per requested recording/evidence). Final source digests: qa/code-hashes.json.
