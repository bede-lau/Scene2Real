# v2 requirement coverage

| Requirement | Evidence | Result |
|---|---|---|
| R-demo | Six registered CCTV MP4s, gpt-image-2 provenance, prompts and SHA-256; contact sheet inspected | Generated. Exact cross-camera physical identity unverified. |
| R-input | tests/test_multivideo.py; three-view browser intake; single-view first slice | Pass: 1–3 sources, atomic validation and >3 rejection. |
| R-analysis | Final live incident reports; raw browser comparison; Cosmos/uncertainty regressions | Processing/provenance pass. Localization and physical coverage unverified. |
| R-target | Group/slot/exclusion server regressions and actual browser confirmation | Pass for operator-authored hypotheses; no calibration claim. |
| R-plan | Final real API plans; tests/test_planner_mobile.py; Astra independent review | Pass: actual Astra, strict schema, complete target coverage, R1 prompt, fail-closed provider behavior. |
| R-simulation | Eight completed simulations, trajectories and MP4 frame review; mobile/rendering tests | Pass for scripted proxy, not full R1 dynamics. |
| R-metrics | Two 32-check acceptance reports; collision/aim/LOS/exposure failure regressions; browser verdict | Pass for confirmed template targets. |
| R-verify | 83 Python tests, focused Node checks, eight live mechanical runs, responsive/browser review | Mechanical verification pass; visual limitations explicitly retained. |
