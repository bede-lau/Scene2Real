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
