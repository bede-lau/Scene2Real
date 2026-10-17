# Scene2Real v2 local verification

Later spatial corrections and warehouse UI checks are recorded in [spatial-fix.md](spatial-fix.md). This file preserves the earlier baseline results.

Recorded 2026-10-17T13:25:10.350931+00:00. Base commit `e4f1a0921a354be8c313c3ca2c76cd1e0de386d0`; the integrated source identities are in `evidence/source-sha256.json`. Python 3.12 / existing `.venv`, FastAPI, MuJoCo and system/static FFmpeg; local server at `http://127.0.0.1:8090`. No dependency changes. Browser: ChatGPT in-app Chromium only. Product scope: approved v2 fast-track plus the user's subsequent R1 and API CCTV requests; separate mockups explicitly waived.

## Verified results

- `.venv/bin/python -m pytest -q`: exit 0, **83 passed**, two existing FastAPI startup deprecation warnings.
- `node tests/frontend_evidence_check.cjs`: exit 0. Verbatim raw output, complete validated uncertainty, selected/incident cache provenance, legacy fallback reason, measured PASS/FAIL and rule.
- `node --check static/app.js` and `git diff --check`: exit 0.
- `scripts/acceptance_multiview.py --run-id r_20261017_142017_0a99 --expected-targets 4 --repeats 3 --out output/qa-v2/final-set1-acceptance.json`: exit 0, **32 checks**. Real uncached Cosmos/YOLO, actual GPT-6 Astra, four operator-confirmed template targets, four completed deterministic simulations and decodable recordings.
- Same runner for `r_20261017_141959_2937`, expected targets 3, repeats 3: exit 0, **32 checks**, three operator-confirmed template targets. Both reports are retained in `evidence/`.
- All eight mechanical runs started at the station, travelled, articulated the legs, sprayed all confirmed targets for >=2 seconds continuously within aim/range/line-of-sight constraints, and recorded zero unintended contacts. Reset removed the old recording; repeated numeric metrics and trajectory hashes matched exactly.
- Actual MP4 frame review: station at 0s; visible blue stream at 3.33s; first target absent at 5.07s; all target markers absent at 33.2s. `output/qa-v2/final-recording-event-review.jpg`.
- Browser journey: three registered clips selected and loaded; live analysis; manually revised cross-view proposals; authored slots confirmed; Astra-generated instruction/model/robot reference; Run; recording; per-target outcomes. Final raw V2 panel text compared byte-for-byte with saved server evidence and matched.
- Replay speed controls selected 2x and 4x; the actual recording HTML media element reported playbackRate 2 and 4, decoded width 960, readyState 4 and no media error. Interactive 4x selection and keyboard Home/PageUp scrubbing worked. Reload restored source/evidence/targets/plan/results, and stage navigation retained the incident hash.
- Responsive check at 1440x1000 and 390x844: inspected simulation and metrics plus mobile evidence; no document horizontal overflow at 390px. Per-view selector and keyboard controls remained usable. Actual pending messages distinguished Astra planning from simulation/export. Browser console warnings/errors: empty.
- Credential-content scan of changed/untracked release files against configured secret values: zero hits. Credentials remain outside the checkout.

## Review and repairs

Independent review used the user's configured OpenAI API with actual `gpt-6-astra` (metadata/findings in `evidence/`). All five findings were repaired: full raw/validated evidence and unknowns; uncertainties from every relevant view in the planner; visible measured verdict/rule; per-view/incident cache provenance; legacy fallback provenance. Added meaningful regression checks and reran the two live incidents after the uncertainty fix. Legacy one-video API behavior remains explicitly compatible; multi-video incidents cannot use its single-target confirmation path.

Browser inspection also found missing verdict styles and stale cached styles. Added responsive verdict styles and versioned app asset URLs, then reloaded and checked computed styles and final screenshots. Existing branding was preserved.

## Limits and unverified outcomes

**These are mechanical pipeline passes, not a claim of perfect visual understanding.** Cosmos v4 fresh preflight matched visible fire counts in 5 of 6 clips; the earlier set-2 center result overcounted. Other fresh outputs varied and several boxes were materially displaced. Full raw responses were kept. Cross-camera associations were manually edited and remain hypotheses because independently generated image views are not calibrated. The tests count confirmed groups; localization, physical correspondence and coverage of every actual fire are **unverified**, not passed. Review notes record the exclusions and assumptions.

The six CCTV clips are API-generated still imagery with local procedural animation, visibly synthetic. The R1 is an authored six-control approximation using official reference dimensions and a BSD-licensed URDF; meshes/full robot dynamics are not loaded. Suppression is an exposure proxy, not fire/fluid physics. W&B/Weave and VAST archival are skipped with explicit telemetry because their credentials are absent. No VM deployment, automated accessibility audit, other-browser verification or zero-defect guarantee is claimed.

## Local visual evidence

- `output/demo_cctv/contact_sheet.jpg` and the six source MP4s / ZIPs.
- `output/qa-v2/final-desktop-station.png`, `final-desktop-metrics.png`, `final-mobile-metrics.png`, `final-mobile-analysis.png`.
- `output/qa-v2/final-set1-acceptance.mp4`, `final-set2-acceptance.mp4`.

Large local artifacts remain ignored. Small acceptance reports, review metadata, notes and source hashes are committed here; the six registered demo MP4s and generation prompts are included under `clips/`.

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

## Integration branch QA — 17 October 2026

Fresh integration evidence is documented in `docs/integration-qa.md`, with source revisions and
machine-readable provenance in `docs/integration-qa/provenance.json`. Existing physics/spatial results
above remain historical. No approval record was created or changed.

233 Python tests, frontend assertions, lock/compile/diff checks passed. Mocked-services/real-physics
browser journey19/19. Final actual live browser16/17: uncertain positive correctly inhibits spray;
positive autonomous suppression remains unverified. Candidate W&B planner19/20overall,15/16locked,
zero collisions, one truncated response rejected. Astra baseline key unavailable; candidate inactive.
New request ledger20W&B/0Astra/6Cosmos. No main merge, deployment, training or policy promotion.
