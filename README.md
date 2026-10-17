# Scene2Real — warehouse-fire footage → repeatable robot rehearsal

VAST Builders Challenge (London, 17 Oct 2026), team 28.

Scene2Real turns a warehouse-fire clip into a measured robot rehearsal:
**video → Cosmos evidence → confirmed target → MuJoCo warehouse → instruction → simulated aim/spray → metrics.**
One page (`/`, the "workbench") walks an operator through the loop; every run is persisted and archived.

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
ssh -L 8090:127.0.0.1:8090 bc-mattlo0546 'cd ~/Scene2Real && bash -lc ./run_vm.sh'   # open http://localhost:8090
```

Secrets are read on the server from `/config/team-28.config` and the VM environment; nothing secret ships to
the browser or the repo. Put the demo clip in `clips/` (optional labels in `clips/clips.json`).

## Inputs

- **Video:** an authorised warehouse-fire MP4 (≤200 MB, 1–120 s), either uploaded or a pinned clip in `clips/`.
  The pre-ingested team corpus contains no warehouse-fire footage (we probed every source video with Cosmos),
  so ingest is a **labelled local upload adapter** whose clips are archived to VAST S3. Analysis is always real Cosmos.
- **Cosmos prompt** `cosmos_fire_obs_v1`: 5 evenly spaced frames, each labelled with its timestamp; strict JSON out.
- **Operator confirmation:** one fire source id + one authored zone (`left_rack`, `right_rack`, `aisle_center`,
  `loading_dock`, `behind_robot`). Cosmos's box suggests a zone; the operator decides.
- **Planner prompt** `plan_v1`: confirmed target + zone + supported skills (`aim_spray_demo` only).

## Outputs

`runs/<run_id>/run.json` (also in VAST S3) holds `run_id, clip_ref, model_id, prompt_id, analysis.raw_text,
observations, confirmed_target, scene, instruction, skill, metrics, timings_s, telemetry`.

- **Observations:** `fire_sources[{id, timestamps_s, bbox_normalized [x_min,y_min,x_max,y_max] 0–1 top-left,
  description, suggested_zone}]`, `unknowns`; cause / scale / depth stay `null` unless observed. YOLO objects are supplementary.
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
| Unit: sim success at 4 reachable zones, `behind_robot` rejected, bad skill/target rejected, deterministic replay | `pytest tests/test_sim.py` | 8 passed |
| Unit: invalid Cosmos JSON → `needs_review` + downstream 409; Cosmos timeout → `failed`/retryable; invalid plan → `blocked`; W&B down → labelled fallback; reset+run identical; Cosmos 0–1000 bbox grid rescaled | `pytest tests/test_pipeline.py` | 12 passed |
| Live: Cosmos endpoint down → `failed`, Retry exposed, scene refused | `scripts/acceptance.py --expect-service-failure` (second server with dead Cosmos URL) | PASS |
| Live: real Cosmos on a non-fire clip → `needs_review`, execution blocked | `scripts/acceptance.py` on a synthetic clip | PASS (0 fire sources) |
| Live: real analysis → simulation, then 3 repeats on the same scene, plus unreachable target blocked | `scripts/acceptance.py --clip-id <demo clip>` | RESULTS_PENDING |

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
