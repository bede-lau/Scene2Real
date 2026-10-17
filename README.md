# Scene2Real — perception-driven robot rehearsal

VAST Builders Challenge (London, 17 Oct 2026), team 28.

Scene2Real turns one to three warehouse-fire video views into a measured robot rehearsal:
**videos → Cosmos evidence → operator-confirmed fires → Astra instruction and plan → MuJoCo rehearsal → recording and metrics.**
The workbench at `/` guides the operator through each stage. The mobile flow is an authored demonstration, not a reconstruction of the incident or a validated real-world firefighting system.

The realistic rehearsal at **`/live.html`** is a live, synthetic warehouse scene: a pinned Unitree G1 model runs in
**MuJoCo**, while Three.js displays the actual articulated geometry, robot camera, nozzle and measurements.
After a run, the workbench's Simulation stage opens it seeded with the first confirmed target
(`/live.html?scenario=left|center|right`). The workbench REST/JSON interface is unchanged.

This is a **perception-driven animated prototype with simplified suppression physics**. Arm motion uses
three **predefined authored poses**, tracked by bounded actuators; it is **not a trained robot policy**.
The robot base is fixed. Warehouse visuals take an industrial simulation direction; this app does not run Isaac Sim.

## Launch the new local simulation

```sh
uv venv .venv
uv pip install --python .venv/bin/python -r requirements.txt
./run_local.sh
# Open http://localhost:8090 (workbench) or http://localhost:8090/live.html (G1 rehearsal)
```

The pinned G1 source assets and converted browser meshes are included. Three.js is vendored locally, so
the new workbench does not need a CDN or an uploaded video. Regenerate assets with
`.venv/bin/python scripts/fetch_g1_assets.py` when necessary.

**Cosmos is disabled for the current local launch, as requested.** Select a scenario and use the Left / Center /
Right arm-pose controls to preview actual MuJoCo motion. Automatic spray remains off without valid inference.
To explicitly enable the live Cosmos path later, set `SCENE2REAL_LIVE_COSMOS=1` and configure the existing
server-side GPU credentials outside the checkout. No fake inference or automatic fallback authorizes spray.

### Live inputs

- Synthetic Three.js scene rendered from the actual MuJoCo robot-camera transform; observer pixels and
  hidden target coordinates are never included in Cosmos image requests.
- Left/center/right fires, no fire, an obscured view, a deliberate wrong-aim scenario, lateral fire position and a blocker.
- Official Menagerie **G1** assets at `62ab00f2bc44f6f20c1c9b7a13f3fb1dd41a4e35` (the supplied URL is G1, not R1),
  with original joint hierarchy/axes/limits and link masses/inertias. Fixed-base and 0.55 kg wrist-tool modifications
  are documented in [assets/unitree_g1/SCENE2REAL.md](assets/unitree_g1/SCENE2REAL.md).

### Live outputs and controls

- Observer orbit camera and persistent robot-camera view; switch the main view between them.
- Quintic transitions between predefined joint references, gravity and finite-force servos at a configured 2 ms timestep.
  Gains are authored demonstration settings, not calibrated physical hardware parameters.
- Actual nozzle-world ray intersections determine hit/miss/blockage. Fire intensity decreases only during
  authorized, unobstructed spray exposure in simulated time. Walls, racks and robot collision geometry block rays.
- New camera requests, scene edits, stale responses, no-fire, uncertainty, invalid output, failure and expired
  decision leases inhibit spraying. Pause, Stop and manual pose preview revoke authorization.
- `runs/live_<session_id>/`: camera JPEGs/hashes, actual raw and validated model responses when inference is enabled,
  response timing, scene edits, joint references/actuals/forces, contact counts, spray hit/miss and intensity traces.
- **Record view** captures a real WebM of the selected simulation camera, saves it with run evidence and provides
  a download. **Export run evidence** downloads current JSON with links to saved files.
- Additive endpoints under `/api/live`: configuration, model manifest, session state, scene/control mutations,
  asynchronous image analysis, evidence and recording. Existing `/api/runs` routes retain their behavior.

### Live evaluation

`pytest tests/test_live_model.py tests/test_live.py` verifies source-model mechanical fidelity, compiled mesh
conversion, three target hits under actual dynamics, blocked/wrong aim without suppression, finite motor forces,
joint bounds, smooth references and fail-closed decision handling. Inference fixtures in unit tests are explicitly
**mocked-only**, not evidence of actual Cosmos use. The current local launch intentionally performs no inference.

See [.prd-to-production/physics-plan.md](.prd-to-production/physics-plan.md) for the integration map and
GhostGUI/parallel-work references. G1 meshes retain their [BSD-3-Clause license](assets/unitree_g1/LICENSE);
the local Three.js runtime retains its [MIT license](static/vendor/THREE-LICENSE.txt).

## Original video workflow

The sections below document the video workbench at `/`.

## Tools used

| Tool | Role |
|---|---|
| NVIDIA Cosmos (`nvidia/cosmos3-nano-reasoner`) | Reads five timestamped frames per view and proposes fire evidence and cross-view associations. |
| CoreWeave | Hosts Cosmos-Reason (`:8001`) and supplementary YOLO11 (`:8002`). |
| OpenAI API | `gpt-6-astra` reviews fire locations, proposes supported cross-view matches and produces the mobile instruction and constrained plan; `gpt-image-2` generated the demo still imagery. |
| Weights & Biases | Optional Weave tracing; legacy single-target planning uses W&B inference or its labelled fallback. |
| VAST Data | Optional S3 archive of run artifacts. |
| MuJoCo | Runs the authored scene, scripted robot and measurement checks. |

## Architecture

```text
static/ workbench  ──HTTP──▶  scene2real/app.py ──▶ pipeline.py (state + persistence)
                                                      ├─ ingest.py: validate and sample each video
                                                      ├─ cosmos.py + yolo.py: per-view evidence
                                                      ├─ grounding.py + matching.py: spatial review and conservative association
                                                      ├─ planner.py: Astra instruction and validated plan
                                                      ├─ mobile.py: authored scene, motion and metrics
                                                      ├─ rendering.py: simulation MP4
                                                      └─ records.py: run files, optional VAST/Weave
```

States are `uploaded → analysed → confirmed → scene_ready → completed`, with `needs_review`, `blocked` and `failed` for problems. Server-side gates prevent later stages from running early. The [build contract](CONTRACT.md) documents the API and the retained legacy single-video path.

## Setup & run

On the team VM, install the dependencies, cache the video tools, and forward the local port:

```bash
rsync -az --exclude .venv --exclude .git --exclude runs ./ bc-mattlo0546:~/Scene2Real/
ssh bc-mattlo0546 'cd ~/Scene2Real && uv venv -p 3.12 .venv && uv pip install -p .venv -r requirements.txt'
ssh bc-mattlo0546 'cd ~/Scene2Real && .venv/bin/static_ffmpeg_paths'
ssh -L 8090:127.0.0.1:8090 bc-mattlo0546 'cd ~/Scene2Real && bash -lc ./run_vm.sh'
```

Open `http://localhost:8090`. For local development, create `.venv`, install `requirements.txt`, run `.venv/bin/static_ffmpeg_paths`, then `./run_local.sh`. Ingest and recording need `ffprobe` and `ffmpeg`; system binaries on `PATH` are preferred, with [static-ffmpeg](https://github.com/zackees/static_ffmpeg) as a dependency fallback.

Secrets stay on the server and must not be committed or sent to the browser. The VM reads `/config/team-28.config` and the environment. Locally, the launcher reads `${XDG_CONFIG_HOME:-$HOME/.config}/scene2real/team.config` or `TEAM_CONFIG`; keep that file mode `600`. Configure `GPU_BEARER_TOKEN` for Cosmos/YOLO and `OPENAI_API_KEY` for spatial review and the mobile planner. `ASTRA_MODEL` defaults to `gpt-6-astra`; set it in the server environment when needed. `SCENE2REAL_SPATIAL_REVIEW` defaults to `auto`, enabling API grounding when the key is configured; `1` requires it and `0` retains unreviewed legacy boxes. Restart after changing configuration. When enabled, a failed or invalid spatial review blocks analysis rather than silently falling back to Cosmos boxes. The mobile flow requires Astra and reports a retryable provider error instead of silently substituting a plan. W&B and VAST credentials are optional for tracing and archival; their absence is reported in telemetry.

## Inputs and use

1. Select one to three pinned clips, upload MP4s, or combine the two, for a single incident. Each MP4 must be 1–120 seconds and no larger than 200 MB. The team corpus has no warehouse-fire footage, so this demo uses a labelled local upload adapter. Synthetic demos are clearly labelled.
2. Analyse. Cosmos prompt `cosmos_fire_obs_v4` processes five timestamped frames per view and preserves raw responses, validated observations, scene/fire descriptions and unknowns. With spatial review enabled, Astra independently reviews the sampled frames and supplies effective fire sightings (`A1`, `A2`, …), frame-specific normalized boxes and model/prompt provenance; the original Cosmos observations remain available for audit. YOLO detections are supplementary. Each view retains its own evidence and failures; incomplete analysis blocks confirmation.
3. Review the images and evidence, group sightings of the same fire across views, exclude false positives with a reason, and choose an authored zone and slot for each physical target. Every sighting must be accounted for. Image boxes stay separate from template positions; uncalibrated metric depth is always `null`.
4. Generate the instruction and scene. Astra receives reviewed evidence and target positions, and returns a strictly validated supported plan. Run the simulation and inspect the recording, 1×/2×/4× playback and per-fire metrics.

Cross-view proposals require Astra to identify persistent shared landmarks and a supported viewpoint relationship, followed by a conservative background-feature and projective-consistency check. The system abstains when support is insufficient and leaves sightings for manual review. These proposals are not calibrated 3D reconstruction or confirmed physical-fire counts. Overlays use boxes associated with the selected sampled timestamp; a sighting without a box for that sample is hidden.

The six CCTV-style fixtures are two intended incidents with three fixed elevated views each. They use OpenAI `gpt-image-2` API-generated still imagery, locally animated, compressed and marked synthetic; they are not native AI-generated video or real CCTV footage. Independent image edits changed scene features between views, so these fixtures do not establish physical-fire correspondence or camera calibration. Generation details and hashes are recorded in [demo provenance](clips/demo_cctv_provenance.json); operator review remains necessary.

## Outputs

A run stores source clips, `run.json`, scene XML, trajectory JSON and, after a mobile simulation, `simulation.mp4` under `runs/<run_id>/`. The run records `video_refs` and the legacy first `clip_ref`, per-view raw/validated Cosmos output and status, spatial-review output and provenance, original Cosmos association suggestions for audit, selected association proposals and uncertainties, evidence warnings, reviewed `confirmed_targets` and exclusions, association and template placement provenance, instruction/model/prompt, skill, metrics, timings and telemetry. VAST archival is attempted when configured.

The authored `wh_mobile_v1` scene starts a robot at a charging station, follows a scripted aisle route, and sprays each confirmed fire. Its appearance uses published Unitree R1 dimensions and an official BSD-licensed reference URDF; the 42 referenced meshes are not bundled, and the simulator uses an authored reduced six-DOF proxy rather than the full 26-DOF robot. See [Unitree R1 reference](docs/unitree-r1.md). The station, nozzle and firefighting ability are demo additions.

The mobile success rule is computed from simulation samples: **every target receives at least 2.0 seconds of continuous valid spray exposure and there are zero unintended collisions**. Valid exposure requires aim, range and line of sight; metrics include each target's exposure, suppression time and failure reason, total targets suppressed, travel distance, duration and contacts. Walking is scripted and suppression is an exposure proxy; neither is validated fire/fluid physics. Playback can be sped up without changing the measured simulation.

## Evaluation

Run `.venv/bin/python -m pytest` for the regression suite and `node tests/frontend_evidence_check.cjs` for focused evidence/provenance/verdict checks. The latest regression run passed 141 tests. Coverage includes video validation and coordinate conversion, spatial-review failures and timestamped boxes, conservative association, grouped confirmation, per-view uncertainty propagation, invalid or unavailable Astra plans, deterministic mobile motion, contact/suppression failure and MP4 export.

The spatial-fix rerun matched all 21 independently annotated fires across six frames at 2.5 s, using IoU ≥0.5 (minimum 0.7318). This is a small synthetic, single-frame check with approximate annotations, not a general accuracy estimate. Run `scripts/check_spatial_accuracy.py` with the two run IDs to reproduce the comparison.

Both CCTV sets completed uncached Cosmos/YOLO, real Astra grounding and planning, simulation and MP4 export. Matching abstained on their inconsistent camera views; each rehearsal used separate V1 sightings and explicitly excluded V2/V3 rather than asserting cross-camera identity. Each passed four deterministic simulation runs. A separate projective same-video control produced four correct automatic three-view groups, including different sighting IDs, and passed four more runs. These control results do not establish matching across independent physical cameras. Browser checks covered raw evidence fidelity, updated warehouse labels, simplified analysis, timestamps in Confirm target, 4× playback, replay and responsive layout. See [spatial QA](.prd-to-production/qa/spatial-fix.md), [earlier QA](.prd-to-production/qa/results.md) and `scripts/acceptance_multiview.py`.

Visual review remains necessary: models can miss or misplace evidence, and the independent fixture edits do not establish cross-camera identity. Confirmed groups and positions are operator decisions; passing mechanical QA does not prove coverage of every physical fire. Raw failures and review notes are retained. Stage latencies are saved in `run.json`; Weave tracing and VAST archival require their own credentials. No real-time performance claim is made.

## PRD-to-production workflow

Bede's personal PRD-to-production skill is bundled in this repository, including
its phase guides, approval and verification helpers, and pinned upstream resources.
No personal skill installation is required.

[CLAUDE.md](CLAUDE.md) loads the complete workflow from
[SKILL.md](.claude/skills/prd-to-production/SKILL.md). Claude Code also discovers it
as a project skill in `.claude/skills/prd-to-production/`.

### Use it

Clone or pull this repository, open Claude Code in its root, and provide your PRD:

```text
/prd-to-production path/to/your-prd.md
```

Follow the staged workflow: approve the compact PRD, review and approve desktop
and mobile mockups for every page/tab, then build and verify against the approved
scope. A repository checkout does not grant those product approvals.

The helpers require Python 3.9 or newer and use only the standard library. Run
these commands from the repository root:

```sh
python3 .claude/skills/prd-to-production/scripts/sources.py verify
python3 .claude/skills/prd-to-production/scripts/workflow.py --help
```

When starting a PRD build, initialize and inspect its durable artifacts:

```sh
python3 .claude/skills/prd-to-production/scripts/workflow.py init --root .
python3 .claude/skills/prd-to-production/scripts/workflow.py status --root .
```

Artifacts and approval records live in `.prd-to-production/`. Other coding agents
can read `CLAUDE.md`, the bundled `SKILL.md`, and the relevant phase guides directly.
Rendering mockups and testing an app still require the appropriate browser tools
and the dependencies selected for that app.

### Included resources

| Resource | Location |
| --- | --- |
| Complete workflow | [SKILL.md](.claude/skills/prd-to-production/SKILL.md) |
| PRD compaction and inventory | [compact.md](.claude/skills/prd-to-production/references/compact.md) |
| Mockup and design guidance | [design.md](.claude/skills/prd-to-production/references/design.md) |
| Implementation and acceptance checks | [build-verify.md](.claude/skills/prd-to-production/references/build-verify.md) |
| Upstream source map and usage guidance | [sources.md](.claude/skills/prd-to-production/references/sources.md) |
| Approval and artifact helper | [workflow.py](.claude/skills/prd-to-production/scripts/workflow.py) |
| Source lookup and integrity helper | [sources.py](.claude/skills/prd-to-production/scripts/sources.py) |
| Exact upstream revisions, URLs, licenses, and hashes | [sources.lock.json](.claude/skills/prd-to-production/sources.lock.json) |
| Codex display metadata | [openai.yaml](.claude/skills/prd-to-production/agents/openai.yaml) |

The offline reference bundle contains 30 pinned files from OpenDesign, Impeccable,
ReUI, coss ui, and CopilotKit, including their original license files. It is a
curated reference bundle; component examples may require additional dependencies
when adapted into an app. The original skill and its bundled resources are
preserved unchanged.

OpenDesign and Impeccable retain Apache-2.0 notices; ReUI and CopilotKit retain MIT
notices; the bundled coss source retains its AGPL-3.0 license. Preserve applicable
notices and review the source's license when reusing it. Bundling these resources
does not assign a new license to Scene2Real.

Claude Code integration follows its official
[project instruction imports](https://code.claude.com/docs/en/memory#import-additional-files)
and [project skills](https://code.claude.com/docs/en/skills) documentation.

## Integrated workflows and planner providers

The integration branch keeps the multi-video workbench at `/` and the separate fixed-base G1
rehearsal at `/live.html`; `/legacy.html` redirects to `/`. Three.js renders MuJoCo state only.
The authored R1 mobile workflow supports scripted walking and up to twelve targets; the Menagerie
G1 workflow supports fixed-base authored arm poses and its own ray-hit intensity rule. They are
separate capabilities, models, asset hashes and outcome contracts.

A workbench handoff calls `POST /api/live/from-incident` with `parent_run_id`. The server accepts
only a complete, confirmed single target at an exactly supported G1 anchor. Current R1 zone/slot
anchors are different, so those incidents receive an explicit `unsupported_mode` result without
moving a target or losing additional targets; use the existing mobile rehearsal instead. Opening
`/live.html` directly remains an independent manual preview and grants no spray permission.

Mobile instruction configuration (server environment; `.env` is not automatically loaded):

```bash
# Existing baseline, default:
SCENE2REAL_PLANNER_PROVIDER=astra
# Explicit candidate; not promoted by this integration:
SCENE2REAL_PLANNER_PROVIDER=wandb
SCENE2REAL_WANDB_PLANNER_MODEL=openai/gpt-oss-20b
# Or Astra remains active and candidate cannot affect motion:
SCENE2REAL_PLANNER_PROVIDER=shadow
```

The hosted candidate uses `WANDB_BASE`, `WANDB_API_KEY` and the `OpenAI-Project` header derived
from `WANDB_TEAM/WANDB_PROJECT` (default `vastdata/team-28`). Schema-constrained output is the
verified default for the tested model; an explicitly selected `SCENE2REAL_WANDB_OUTPUT_FORMAT=prompt_json`
permits another compatible model to use prompt JSON with the same independent validator. There
is no automatic format downgrade, model race or cross-provider fallback in the mobile path.
The 8192-token default increases the earlier output budget, but truncation remains possible and is always
rejected. HTTP timeouts/transient errors have at most two configured attempts; 401 and malformed
or invalid output are not silently retried or converted into executable fallback instructions.

Astra still owns vision grounding and conservative cross-view matching. Selecting W&B for the
text planner does not replace those image-capable stages or remove their OpenAI credential needs.
Missing W&B credentials do not affect the default baseline; explicitly selecting unavailable W&B
blocks scene planning with an actionable error. `SCENE2REAL_LIVE_COSMOS=0` is the default, and manual
G1 pose previews never authorize spray. Enable it only for explicit live verification.

## Reproducible integration checks

Use a project-local Python environment. `requirements.txt` is the lightweight application/test
install; `pyproject.toml`/`uv.lock` retain the broader legacy sponsor-tool extras and now explicitly
declare the already required FastAPI/MuJoCo runtime. No global installation is required.

```bash
uv venv .venv --python 3.12
uv pip install --python .venv/bin/python -r requirements.txt
MUJOCO_GL=egl .venv/bin/python -m pytest tests -q
node tests/frontend_evidence_check.cjs
.venv/bin/python -m evals.runner --output output/new-offline-campaign
# Explicit, metered network evaluation; never reuses an existing campaign directory:
MUJOCO_GL=egl .venv/bin/python -m evals.runner --live --output output/new-live-campaign
# Serve locally for browser acceptance (not a deployment):
MUJOCO_GL=egl .venv/bin/python -m uvicorn scene2real.app:app --host 127.0.0.1 --port 8094
node scripts/integration_browser.cjs
```

The browser script accepts `BASE_URL`, `OUT`, `PLAYWRIGHT_MODULE` and `CHROME_PATH` environment settings;
use an existing Playwright/Chrome runtime or install browser tooling into your development environment.
No second browser simulation, training, reinforcement learning or new frontend framework is used.

Each run retains local JSON/JSONL, immutable evidence hashes, VAST archive paths and best-effort Weave
milestones linked by stable run/session/parent IDs. Provider calls under those contexts also receive
supported Weave attributes. Independent HTTP requests are linked events rather than a fictitious
single nested trace. Bounded logging queues cannot authorize motion or block the physics worker;
status exposes errors/drops and SDK submission does not claim remote persistence. Set
`SCENE2REAL_WEAVE=0` to disable remote initialization. Never put secrets in repository files.

See [integration plan](docs/integration-plan.md), [measured QA](docs/integration-qa.md), and
[proposed PR](docs/integration-pr.md). The active baseline remains Astra. The fresh candidate campaign
and separate manual/mocked/live browser evidence are explicitly labelled; older physics/spatial and
25/30 evaluation artifacts remain historical evidence under their original source revisions.
