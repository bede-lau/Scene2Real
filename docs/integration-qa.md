# Integration QA — 17 October 2026

**Decision: implementation ready for review; Astra remains active. No deployment or main merge.**
The W&B candidate is not promoted: a live Astra baseline comparison was unavailable and final G1
positive autonomous suppression was conservatively blocked by an uncertain response.

## Source and review boundaries

Main `cdf6adf641e905c5a75a1232db1d65a54ee26368`, simulation
`8a4e03d` (full SHA in [provenance](integration-qa/provenance.json)). The refreshed merge base is main.
The first independently reviewable merge is `a7928f2`, with entry-point corrections and documentation
in `b71c168`. Provider selection is `18bf485`; R1 travel correction `a6eda96`; strict live adapter
`af75e2a`; correlated telemetry `e5c4b01`; context/redaction `18c1d3a`; nonblocking live evidence and
freshness `89da135`; mock-provenance UI `b4aa0b7`; evaluation tooling `d0b9cf7`.

The model campaign ran at `e5c4b01`, with exact source hashes in its manifest. Subsequent source
changes concern telemetry, lock boundaries, environment/dependencies and visible mock provenance;
planner request/controller code was not tuned against the locked test. Final live browser source is
`89da135`; final mocked UI source is `b4aa0b7`, with source-file hashes saved beside each report.
Existing main spatial-QA and simulation evidence are historical and have not been relabelled.

## Local regression and browser evidence

| Check | Result | Evidence |
|---|---|---|
| Phase1 before provider changes | 169 Python tests; frontend checks passed | `output/integration/phase1/` |
| Final Python suite | **233 passed**, four existing FastAPI lifecycle deprecation warnings | `output/integration/final-pytest.xml` |
| Frontend evidence assertions | Passed, including explicit mocked provenance | `output/integration/final-frontend.log` |
| Local dependency lock | `uv lock --check` passed | `output/integration/final-lock.log` |
| Compile/diff checks | `compileall` and `git diff --check` passed | run locally on integration tree |
| G1 deterministic physics controls | **6/6** | campaign `g1-controls.json`; explicit fixture authorization, no inference claim |
| Full mocked-service browser journey | **19/19** | [report](integration-qa/mocked-browser.json), real ingest/confirmation/physics/export |
| Final live-service browser | **16/17** | [report](integration-qa/final-live-browser.json), uncertainty retained as failure |
| Existing multiview acceptance script | Expected real-provider gate failed on mocked fixture | [provenance](integration-qa/acceptance-provenance.json) |

The unmodified multiview script successfully checked completed mobile operation and retained views,
then correctly failed its requirement for real uncached Cosmos/YOLO. Its hardcoded live-provider
report label is explicitly corrected by the adjacent provenance file. This is not a live acceptance pass.
Grounding/matching regression tests cover support, inappropriate merges and abstention; no fresh
Astra association call was made and no independently established multi-view physical identity is claimed.

Browser verification used Chrome 155 via existing cached Playwright and an existing local Node binary.
There were no browser JavaScript errors or broken application assets. It checked `/`, `/live.html`,
`/legacy.html`, reciprocal navigation, uploads, grouping/exclusions, scene/run/replay and MP4 export,
observer versus robot-camera capture, G1 meshes, pause/stop/manual-preview revocation, downloads and
responsive layouts. The test-only fixture app is a separate explicit entry point with mocked model
services; it is never the default server. All verification servers on ports8094–8096 were stopped.

[Workbench completed screenshot — mocked services](integration-qa/workbench-mocked-completed.png) ·
[G1 desktop](integration-qa/g1-desktop.png) · [G1 mobile](integration-qa/g1-mobile.png) ·
[Actual G1 manual-preview recording](integration-qa/g1-manual-preview.webm) ·
[Actual Python mobile export — mocked services](integration-qa/mocked-services-real-physics.mp4).

## Fresh planner campaign

Dataset `integration_v1`, SHA256
`c79a5a4e7fc0368aa75112e1edac2e3038a19948f4669359e83e3b4f964264c1`:
four development cases and eight locked synthetic reviewed incident families, repeated twice.
The same reviewed inputs are available to either provider. No hidden labels enter either prompt.
No tuning occurred between locked trials. Repeats are correlated, not independent real-world evidence.

| Provider | Development | Locked test | Collisions |
|---|---:|---:|---:|
| W&B `openai/gpt-oss-20b` | 4/4 valid and successful | **15/16 valid and successful (93.75%)** | 0 |
| Deterministic reference | 4/4 | 16/16 | 0 |
| Active Astra baseline | unavailable | unavailable | not measured |

One locked response hit the 8192-token output limit and was rejected before scene execution. Increasing
from the historical 1600 limit mitigated but did not eliminate truncation; no invalid completion was
salvaged or retried to improve its reported score. Candidate output varied in 6/8 repeated families.
All 39 valid plans had identical saved-plan replay and agreement with the independent MuJoCo-qpos
nozzle/range/occlusion/contact continuous-exposure audit. Candidate median inference latency was
4.256s development and3.508s locked, with52,348 provider-reported tokens. Monetary cost is unverified.

The reference is an authored deterministic plan, **not** a substitute for the missing active Astra
comparison. `OPENAI_API_KEY` was absent. Candidate selection/promotion therefore remains blocked.
The earlier 29/30-valid,25/30-success campaign was verified from its6036c8f artifact hashes and used
only as historical diagnosis, never as untouched test data for this build.

The historical backward-target collision was independently reproduced in the current pre-fix controller:
`robot_forearm|robot_torso`. The predefined forward carry pose during non-spray traversal removes
that collision on the exact replay. Contact masks/checks and success rules were unchanged. Boundary-speed,
obstacle, occlusion and collision tests still pass. [Before/after replay](integration-qa/collision-diagnosis.json).

- [W&B development evaluation](https://wandb.ai/vastdata/team-28/r/call/01a14a56-2f14-74d8-a69d-532aff8d63a0)
- [W&B locked evaluation](https://wandb.ai/vastdata/team-28/r/call/01a14a56-7d1f-71c2-b0e9-54eabc1474e8)
- [Deterministic locked reference](https://wandb.ai/vastdata/team-28/r/call/01a14a56-1551-73b5-b4e8-69500401fd2f)

## Fresh perception and G1 boundary

Exactly **20 W&B, 0 Astra and 6 Cosmos requests** were made in this integration campaign. This is
separate from the earlier83-W&B/7-Cosmos campaign. No training or reinforcement learning occurred.
The six Cosmos requests comprise two initial G1 camera checks, two video checks and two final G1 checks.

The video-only check recognized a synthetic annotated positive clip (four sightings) and a synthetic
no-fire clip (zero sightings). Incident detection was 2/2. Five timestamped images per clip were sent;
no unsupported Cosmos video-sampling options were used. The static Cosmos boxes lack `bbox_at_s`, so
**exact-timestamp localization remains unscored**. The earlier trace's static-box 1/4 diagnostic must
not be read as exact-frame IoU; [scoring correction](integration-qa/video-scoring-notes.json) preserves
raw outputs and explains that boundary. No real-world source-footage reliability or cross-camera truth
is claimed.

Final G1 visible-fire inference returned `uncertain` with `Extent of fire spread` among unknowns.
The existing conservative uncertainty selector inhibited automatic spray: hit time 0 s, intensity 1.
The final no-fire inference returned `no_fire` and kept spray off. Earlier G1 inference produced
`ready`, but it was not held long enough to measure suppression and predates the final trace/lock
changes. **No final live positive autonomous suppression claim is made.** Deterministic physics
controls separately demonstrate actual hit-dependent intensity reduction and blocked/wrong-aim behavior.
See [uncertain positive screenshot](integration-qa/g1-positive-uncertain.png).

- [Actual video positive trace](https://wandb.ai/vastdata/team-28/r/call/01a14a5b-106b-723d-b274-117e5678b97f)
- [Actual video no-fire trace](https://wandb.ai/vastdata/team-28/r/call/01a14a5b-34f0-747e-9554-3d0dbe2d1903)

The final session's21 milestone events and two actual Cosmos calls were verified persisted and
readable without credentials, linked by `session_id=4988acefed6c` and its snapshot/revision attributes.
[Final visible-fire/uncertain Cosmos call](https://wandb.ai/vastdata/team-28/r/call/01a14a5c-86a7-793d-84d5-ed610c4e7908) ·
[Final no-fire Cosmos call](https://wandb.ai/vastdata/team-28/r/call/01a14a5c-bba7-7c29-b71c-cd38effec2cb).
[Linked milestone references](integration-qa/live-trace-links.json).

## Reproduce and review

```bash
MUJOCO_GL=egl .venv/bin/python -m pytest tests -q
node tests/frontend_evidence_check.cjs
uv lock --check
MUJOCO_GL=egl .venv/bin/python -m evals.runner --output output/new-offline
# Explicit metered network use only; fresh output dir,20 requests/provider maximum:
MUJOCO_GL=egl .venv/bin/python -m evals.runner --live --output output/new-live
```

The default remains Astra, live Cosmos remains off, and current R1 anchors cannot silently seed G1.
The strict handoff explains unsupported mode and retains the mobile workflow. Review stage1 merge
independently, then review the opt-in provider/tracing/evaluation changes. See [proposed PR](integration-pr.md).
