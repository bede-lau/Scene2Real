# First real slice
- Approved revision: v2 + user-authorized fast-track; local native-HTML design retained.
- Real slice: run r_20261017_140400_db30: one MP4 -> uncached Cosmos + YOLO -> explicit mobile confirmation -> real gpt-6-astra -> MuJoCo mobile trajectory -> H.264 recording -> measured PASS.
- Stored evidence: output/qa-v2/first-slice-analysis.json, first-slice-plan.json, first-slice-complete.json; runs/r_20261017_140400_db30/simulation.mp4.
- Observed: start at station, 1.5m travel, one suppressed target, >=2s measured exposure, zero unintended contacts; recording downloadable. Browser exposed Astra provenance, 1x/2x/4x controls and per-fire QA.
- Validation regression: atomic 1–3 sources, invalid views, reused group membership, duplicate slots, exclusions, legacy multiview bypass, strict Astra target/settings, contact/LOS/exposure and encoder failures covered in focused automated tests.
- Repairs before broader acceptance: excluded evidence target mapping, legacy multiview confirmation bypass, replay water/measurement agreement, self/floor contact accounting, missing demo selection.
- Remaining: full both-set browser journeys, repeated numeric replay, mobile layout and final code digest/evidence.

# First-slice check

17 Oct2026. Browser plugin absent; existing Playwright1.62.1 + installed Chrome used with escalation because sandbox Chrome aborts. No browser dependency installed.

First slice: model manifest -> authoritative live state -> actual two-camera Three.js rendering -> scenario/pose control. Browser ready condition is body[data-ready=true], not network-idle (the app polls state).

Desktop1440x1000 and mobile390x844: meaningful content; two actual WebGL canvases; no framework/error overlay; no console errors or failed requests in initial capture. Mobile document has no horizontal overflow. Original first camera framing obscured the robot behind a rack/column; fixed homeCamera to(-2.8,-3.4,2.3),target(1.25,0,.80) and inspected corrected screenshots. Fire transforms update synchronously before snapshot capture.

Functional first slice: left/right/center scene positions and actual joint states change; manual pose does not authorize spray. Observer/robot camera switching works. Server state.obstacle added after independent QA found checkbox/display disagreement; updated backend now exposes physical blocker state. Retained pending mutation ownership through monotonic state sequence checks.

Form/route-specific risks such as duplicate database entities, modal drafts and Back navigation during commits are absent: this slice has native scenario/pose controls and session state, no create/edit forms or modal navigation. Scene mutation validation is server-authoritative and tested for atomic invalid rejection.

Evidence initial/corrected actual screenshots: /private/tmp/scene2real-live-qa/desktop-first.png and mobile-first.png. Final integrated browser report and recording pending qa/results.md.
