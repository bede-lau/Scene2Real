# First-slice check

17 Oct2026. Browser plugin absent; existing Playwright1.62.1 + installed Chrome used with escalation because sandbox Chrome aborts. No browser dependency installed.

First slice: model manifest -> authoritative live state -> actual two-camera Three.js rendering -> scenario/pose control. Browser ready condition is body[data-ready=true], not network-idle (the app polls state).

Desktop1440x1000 and mobile390x844: meaningful content; two actual WebGL canvases; no framework/error overlay; no console errors or failed requests in initial capture. Mobile document has no horizontal overflow. Original first camera framing obscured the robot behind a rack/column; fixed homeCamera to(-2.8,-3.4,2.3),target(1.25,0,.80) and inspected corrected screenshots. Fire transforms update synchronously before snapshot capture.

Functional first slice: left/right/center scene positions and actual joint states change; manual pose does not authorize spray. Observer/robot camera switching works. Server state.obstacle added after independent QA found checkbox/display disagreement; updated backend now exposes physical blocker state. Retained pending mutation ownership through monotonic state sequence checks.

Form/route-specific risks such as duplicate database entities, modal drafts and Back navigation during commits are absent: this slice has native scenario/pose controls and session state, no create/edit forms or modal navigation. Scene mutation validation is server-authoritative and tested for atomic invalid rejection.

Evidence initial/corrected actual screenshots: /private/tmp/scene2real-live-qa/desktop-first.png and mobile-first.png. Final integrated browser report and recording pending qa/results.md.
