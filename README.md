# Scene2Real — perception-driven robot rehearsal

VAST Builders Challenge (London, 17 Oct 2026), team 28.

The default page (`/`) is now a live, synthetic warehouse rehearsal: a pinned Unitree G1 model runs in
**MuJoCo**, while Three.js displays the actual articulated geometry, robot camera, nozzle and measurements.
The original video → Cosmos → confirmation → simulation workbench remains at **`/legacy.html`** with its
existing REST/JSON interface unchanged.

This is a **perception-driven animated prototype with simplified suppression physics**. Arm motion uses
three **predefined authored poses**, tracked by bounded actuators; it is **not a trained robot policy**.
The robot base is fixed. Warehouse visuals take an industrial simulation direction; this app does not run Isaac Sim.

## Launch the new local simulation

```sh
uv venv .venv
uv pip install --python .venv/bin/python -r requirements.txt
./run_local.sh
# Open http://localhost:8090
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

The sections below document the preserved video workbench at `/legacy.html`.

## Sponsor tools used

| Sponsor | Role in this project |
|---|---|
| NVIDIA Cosmos (`nvidia/cosmos3-nano-reasoner`) | Reads 5 time-stamped frames and returns fire-source evidence: ids, timestamps, normalised boxes, unknowns (`scene2real/cosmos.py`) |
| CoreWeave | GPU hosting for Cosmos-Reason (`:8001`) and YOLO11 (`:8002`, supplementary object detections) |
| Weights & Biases | Hosted inference (`meta-llama/Llama-3.1-8B-Instruct`) writes the instruction + skill plan; Weave traces every stage (`scene2real/planner.py`, `records.py`) |
| VAST Data | S3 archive of each run's clip and `run.json` at `s3://team-28-vss-chunks/scene2real/runs/<run_id>/` |
| Cursor | Development over SSH on the team VM |

## Architecture

```
static/ (workbench, three.js viewer)  ──HTTP──▶  scene2real/app.py (FastAPI)
                                                   └─ pipeline.py  state machine + gating + persistence
                                                       ├─ ingest.py   validate mp4, ffprobe, sample frames
                                                       ├─ cosmos.py   Cosmos-Reason → validated observations
                                                       ├─ yolo.py     YOLO11 supplementary objects (never blocks)
                                                       ├─ scene.py    authored warehouse template wh_aisle_v1 → MJCF
                                                       ├─ planner.py  W&B instruction/plan (labelled deterministic fallback)
                                                       ├─ sim.py      MuJoCo physics, scripted joint targets, metrics
                                                       └─ records.py  runs/<id>/run.json, VAST S3 archive, Weave
```

States: `uploaded → analysed → confirmed → scene_ready → completed`, with `needs_review` (invalid or empty
analysis), `blocked` (invalid plan or unreachable target) and `failed` (service error, retryable). The server
enforces stage gating (HTTP 409); the UI enables only the valid next action. Contract: [CONTRACT.md](CONTRACT.md).

## Setup & run (team VM)

```bash
rsync -az --exclude .venv --exclude .git --exclude runs ./ bc-mattlo0546:~/Scene2Real/
ssh bc-mattlo0546 'cd ~/Scene2Real && uv venv -p 3.12 .venv && uv pip install -p .venv -r requirements.txt'
ssh bc-mattlo0546 'cd ~/Scene2Real && .venv/bin/static_ffmpeg_paths'
ssh -L 8090:127.0.0.1:8090 bc-mattlo0546 'cd ~/Scene2Real && bash -lc ./run_vm.sh'   # open http://localhost:8090
```

Secrets are read on the server from `/config/team-28.config` and the VM environment; nothing secret ships to
the browser or the repo. Put the demo clip in `clips/` (optional labels in `clips/clips.json`).

Video ingest needs both `ffprobe` (validation) and `ffmpeg` (frame extraction). System binaries on
the server's `PATH` are preferred; otherwise the app uses [static-ffmpeg](https://github.com/zackees/static_ffmpeg)
from the Python dependencies. `static_ffmpeg_paths` downloads and caches both binaries for the current
platform; run it during setup while internet access is available. For local development, run
`uv pip install -p .venv -r requirements.txt`, then `.venv/bin/static_ffmpeg_paths` and
`./run_local.sh`. The local launcher reads credentials from
`${XDG_CONFIG_HOME:-$HOME/.config}/scene2real/team.config` (or the file specified by `TEAM_CONFIG`).
Store `GPU_BEARER_TOKEN=<team GPU token>` there with file permissions `600`; never add credentials to
the checkout. This token authenticates both Cosmos and YOLO. Restart the server after changing it.
W&B inference/Weave and VAST archival require their own credentials; without those, the planner uses
the labelled fallback and archival is skipped.

## Inputs

- **Video:** an authorised warehouse-fire MP4 (≤200 MB, 1–120 s), either uploaded or a pinned clip in `clips/`.
  The pre-ingested team corpus contains no warehouse-fire footage (we probed every source video with Cosmos),
  so ingest is a **labelled local upload adapter** whose clips are archived to VAST S3. Analysis is always real Cosmos.
  The optional local `synthetic-warehouse-fire` test clip is a four-second animation of a photorealistic image
  generated with OpenAI `gpt-image-2`; it is labelled synthetic and is not incident footage or native AI video.
  Its prompt, renderer and provenance are saved under `output/imagegen/` and `output/video/`.
- **Cosmos prompt** `cosmos_fire_obs_v2`: 5 evenly spaced frames, each labelled with its timestamp; strict JSON out.
  Native Cosmos `bbox_2d` coordinates use 0–1000 per axis and are converted to canonical 0–1 image regions.
  Legacy `bbox_normalized` inputs must already be in 0–1; validation rejects mislabeled or ambiguous coordinates.
  The response also retains visible scene layout, fire location, burning object, smoke and nearby objects.
  This uncalibrated input adapter always records metric depth as unknown, even if the model guesses a distance.
- **Operator confirmation:** one fire source id + one authored zone (`left_rack`, `right_rack`, `aisle_center`,
  `loading_dock`, `behind_robot`). Cosmos's box suggests a zone; the operator decides.
- **Planner prompt** `plan_v1`: confirmed target + zone + supported skills (`aim_spray_demo` only).

## Outputs

`runs/<run_id>/run.json` (also in VAST S3) holds `run_id, clip_ref, model_id, prompt_id, analysis.raw_text,
observations, confirmed_target, scene, instruction, skill, metrics, timings_s, telemetry`.

- **Observations:** `fire_sources[{id, timestamps_s, bbox_normalized [x_min,y_min,x_max,y_max] 0–1 top-left,
  bbox_source_scale, image_center_normalized, description, location_description, burning_object, smoke_description, nearby_objects,
  suggested_zone}]`, `scene_description`, `unknowns`; unobserved cause / scale stay `null` and metric depth is always
  `null` without calibration. Visual context is passed to the action planner; authored warehouse and robot geometry
  still come from the confirmed zone and template. YOLO objects are supplementary.
- **Confirmed target:** the image box and the template-assumed metric position are stored separately, with provenance.
- **Scene:** template `wh_aisle_v1` (racks, pallets, collision geometry, fire markers, fixed-base humanoid with an
  attached extinguisher), source→zone mapping and per-item placement provenance. Authored geometry; we make no reconstruction claim.
- **Instruction/skill:** text, source (`wandb` + model, or `fallback`, labelled), `{name: aim_spray_demo, target_id}`.
- **Trajectory:** 30 fps poses for every geom plus nozzle ray and spray/fire FX, rendered in the browser with three.js.
- **Metrics:** angle error (final/min), longest hold ≤5°, simulated duration, unintended collisions, success.

## Evaluation

**Success rule (computed from physics only, never from an LLM):** nozzle-to-target angular error ≤5° for ≥2.0 s of
continuous simulated time **and** zero unintended robot/environment collisions (hand↔extinguisher attachment contacts excluded).

| Check | How | Result |
|---|---|---|
| Ingest: validate MP4 and extract 5 frames with an empty `PATH`; reject corrupt MP4; prefer system tools; report setup and process failures | `pytest tests/test_ingest.py` | 5 passed |
| Cosmos: native box conversion and source scale, legacy compatibility, richer observations, ambiguous/invalid coordinates rejected, guessed depth discarded | `pytest tests/test_cosmos.py` | 19 passed |
| Unit: sim success at 4 reachable zones, `behind_robot` rejected, bad skill/target rejected, deterministic replay | `pytest tests/test_sim.py` | 8 passed |
| Unit: invalid Cosmos JSON → `needs_review` + downstream 409; Cosmos timeout → `failed`/retryable; native boxes converted; Confirm validation/persistence; visual evidence reaches planner; invalid plan → `blocked`; W&B down → labelled fallback; reset+run identical | `pytest tests/test_pipeline.py` | 13 passed |
| Merged redesign: real uncached Cosmos + YOLO → Confirm target, raw and validated evidence, timestamp seeking, zone override, invalid target rejection, saved confirmation | Local browser + API checks | PASS (17 Oct 2026; run `r_20261017_133346_71e5`; Instruction deferred) |
| Merged redesign: 4:3 upload keeps video/overlay aligned; non-fire analysis exposes Retry and blocks confirmation; confirmed evidence survives server restart | Local browser + API checks | PASS (17 Oct 2026) |
| Live: Cosmos endpoint down → `failed`, Retry exposed, scene refused | `scripts/acceptance.py --expect-service-failure` (second server with dead Cosmos URL) | PASS |
| Live: real Cosmos on a non-fire clip → `needs_review`, execution blocked | `scripts/acceptance.py` on a synthetic clip | PASS (0 fire sources) |
| Live local upload: authenticated Cosmos + YOLO; non-fire footage → `needs_review`, scene and simulation return HTTP 409 | `POST /api/runs/<id>/analyse`, `/scene`, `/run` | PASS (17 Oct 2026; uncached Cosmos, YOLO `ok`) |
| Live: uncached Cosmos + YOLO on the labelled synthetic fire fixture → simulation, then 3 identical repeats, plus unreachable target blocked | `scripts/acceptance.py --clip-id synthetic-warehouse-fire --zone right_rack --repeats 3` | PASS (17 Oct 2026; planner fallback; W&B/VAST credentials absent) |

Stage latencies are logged in `run.json.timings_s` and in Weave (project `vastdata/team-28`). We make no real-time claim.

**Limitations:** fire and spray are visual effects only (no fluid or suppression physics); the robot is fixed-base with
scripted joint targets (no walking or grasping); zones are authored, not reconstructed from the video; one target per run.

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
