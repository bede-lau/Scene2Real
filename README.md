# Scene2Real — warehouse-fire footage → repeatable robot rehearsal

## Browser training demo

The **Training** link opens `/training.html` in a new tab, keeping the current workbench open. This lightweight proof of concept fits a linear aiming model to generated 2D target positions and compares it with a fixed forward-facing baseline on nine held-out positions. It runs entirely in the browser and does not use footage, MuJoCo, G1 motion, backend training jobs, or real robot controls. Results are not saved and do not demonstrate physical-world performance. The separate local recorded-learning workbench is not part of this demo.

The top-down diagram replays fits after each teaching example and lets the viewer pause, scrub, and choose a held-out target. It is a geometric illustration, not a physics rollout. Run `node --test tests/test_training_demo.mjs` for the fitting, replay and input-boundary checks.

VAST Builders Challenge (London, 17 Oct 2026), team 28.

Scene2Real turns one to three warehouse-fire video views into a measured robot rehearsal:
**videos → Cosmos evidence → operator-confirmed fires → Astra instruction and plan → MuJoCo rehearsal → recording and metrics.**
The workbench at `/` guides the operator through each stage. The mobile flow is an authored demonstration, not a reconstruction of the incident or a validated real-world firefighting system.

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

The public ChatGPT Site hosts the interface and forwards `/api/` to a separate
Python backend. For a backend that stays online independently of a laptop or
the workshop VM, deploy the supplied `Dockerfile` to a managed container host
with a stable HTTPS URL and a persistent volume mounted at `/data`. The image
includes all seven demo clips, MuJoCo, FFmpeg, software OpenGL rendering, and
the authenticated API proxy. It uses the pinned Linux dependencies in
`requirements-production.txt`, compiled from the working versions in
`requirements.txt`.

The container defaults `SCENE2REAL_FFMPEG_THREADS=1` to bound the video encoder
and filter workers' memory use on small services. Values from 1 to 64 are
accepted; outside the container, leaving it unset retains FFmpeg's automatic
thread selection. This changes encoding resources, not Cosmos analysis,
planning, the simulation trajectory, or its measured metrics.

The Vercel/Railway deployment uses Vercel for the static workbench
and a streaming gateway (`ops/vercel_frontend.mjs`), with Railway keeping the
Python worker and a persistent `/data` volume. The root `vercel.json` selects
`Dockerfile.vercel`; Railway keeps using the separate root `Dockerfile`.
Both projects follow `bede-lau/Scene2Real` branch `main`, without a Railway
commit pin or a manual frontend source snapshot. Set Vercel's
`PORT=8080`, `SCENE2REAL_BACKEND_URL` to the
Railway HTTPS origin, and `SCENE2REAL_SITE_TOKEN` privately to the backend's
matching token. Model credentials belong only on Railway. The browser
receives neither the service token nor the model keys. Keep Vercel Deployment
Protection enabled and verify that an unauthenticated API request redirects
to Vercel sign-in. The stable protected URL is
`https://scene2real-workbench-trial-git-main-emanate-projects.vercel.app`.
Every successful Git-triggered main deployment updates this branch URL.

On the current Vercel Hobby plan, main intentionally deploys to the protected
Preview environment. Production tracking is reserved for
`codex/manual-production`, with automatic domain promotion disabled. The
checked-in Git deployment rules allow only `main`; the reserved branch does
not auto-deploy. Do not promote the app onto an unprotected production domain.
Vercel Hobby requires the commit author to match the account owner; use a
verified GitHub email, and owner-authored merge commits for contributions from
other authors. A deploy failure leaves the last successful frontend available.
Backend rollouts use the existing readiness check and persistent volume; an
active in-memory operation interrupted by a rollout still needs to be retried.

Railway Free has a 500 MB memory limit and a 500 MB volume. Fresh full-pipeline
tests exceeded that memory limit, including a slower `GALLIUM_DRIVER=softpipe`
trial. On 25 October, Hobby passed fresh full-pipeline tests for both warehouse
sets with a verified 1 GB runtime limit, one vCPU, one replica, and a 5 GB
persistent volume. The existing $10 compute spending cap remains enabled.
Keep `GALLIUM_DRIVER=llvmpipe`, `LP_NUM_THREADS=1`, `OMP_NUM_THREADS=1`,
`OPENBLAS_NUM_THREADS=1`, and `MALLOC_ARENA_MAX=2`. Set 1 also passed with a
6 MiB direct upload; this is a sequential single-incident test, not a
concurrency or maximum-file-capacity result. Saved metrics and MP4 hashes
survived the required source deployment. Details are in the hosting QA record.
Vercel rejected a 6 MiB video through its gateway with `FUNCTION_PAYLOAD_TOO_LARGE`.
Set Railway's `SCENE2REAL_PUBLIC_ORIGIN` to its HTTPS origin to enable upload
grants. For selections above 3 MiB, the workbench obtains an authenticated,
two-minute, single-use grant through Vercel, then streams the upload directly
to Railway. Grants allow only one multipart `POST /api/runs`, are bound to
the requesting browser origin, and cap the request at three 200 MiB files
plus multipart overhead. The existing per-file/type/count validation still
runs in Python. Grants cannot read runs or invoke inference. The browser
never receives the reusable service token. Deploy the updated workbench and
proxy together; local servers without the grant endpoint retain their
existing upload path. The Python backend should
not use Vercel's ephemeral container disk for saved runs: the cloud trial lost
its test run after preview scale-down, while Railway's volume retained the
completed run and recording across redeployment.

Configure `SCENE2REAL_SITE_TOKEN` as a private random token of at least 32
characters, and supply `GPU_BEARER_TOKEN` and `OPENAI_API_KEY` as runtime
secrets. Optional W&B/VAST settings and model endpoint overrides use the same
configuration names as the local backend. Keep the existing live-Cosmos flag
unless intentionally enabling that feature. Secrets, user uploads, and prior
runs are excluded from the image. The container listens on the host-provided
`PORT` (default `10000`), with `/healthz` available for a health check; API
requests require the bearer token. Run one instance because live sessions and
active jobs remain in process memory. Cosmos and Astra still run at their
configured external model endpoints; this container does not need a GPU.
The entrypoint waits for the local Python API health check before opening the
public authenticated proxy, including when Railway wakes the service from
sleep. A failed or timed-out backend startup fails the container rather than
exposing a proxy without a ready backend. Retrying the workbench's initial
load also clears the previous startup error.

Run records and uploaded/generated videos live in `/data/runs`, and optional
analysis caches in `/data/cache`. Securely copy the prior backend's `runs/`
contents into that volume before cutover. The entrypoint prepares volume
permissions and runs both application processes as UID `10001`. If the host
enforces a non-root entrypoint, provision those writable directories for that
UID first. A restart restores saved runs, while active jobs and live sessions
must be restarted. Verify a full analysis and MP4 render before changing the
Sites runtime `SCENE2REAL_BACKEND_URL` to the new HTTPS origin; keep the same
Sites secret `SCENE2REAL_SITE_TOKEN`, then redeploy the existing frontend
version. A green health check alone does not verify external model access.
See [backend hosting QA](.prd-to-production/qa/backend-hosting.md) for the
container, live-inference, rendering, and restart verification.

For a Linux VM with systemd, install dependencies into `.venv`, create the
mode-`600` `~/.config/scene2real/site-proxy.env` token file, and run
`./ops/install_linux_services.sh` as the application user with non-interactive
sudo access. It creates services scoped to that user on isolated loopback
ports `18090` and `18091`, with saved runs outside the checkout. It refuses
to take over units owned by another deployment. Optional private overrides
belong in `~/.config/scene2real/backend.env`. Set
`SCENE2REAL_TUNNEL_CONFIG` only for a dedicated named-tunnel config routing
to the selected proxy port; it never changes the existing SSH tunnel.

As a local fallback, on the Mac hosting the public Site API, run the backend, authorization proxy,
and named Cloudflare Tunnel as separate launchd services. This keeps them alive
after terminal exits, restarts them after a crash or login, and prevents a
temporary `trycloudflare.com` URL from becoming the production endpoint. The
Mac must still be awake and online.

After installing dependencies and creating the mode-`600` team config, run
`./ops/install_macos_backend_service.sh`. It keeps a private runtime copy under
`~/Library/Application Support/Scene2Real/` because macOS blocks background
services from reading a Desktop checkout. The backend binds only to loopback
port 8090. The Site authorization proxy binds only to loopback port 8091,
requires a random bearer token, and forwards `/api/` operations plus
read-only, allowlisted workbench pages and assets to the backend. Other paths
are rejected. Store the same token in the Sites secret `SCENE2REAL_SITE_TOKEN` and in
`~/.config/scene2real/site-proxy.env` as
`SCENE2REAL_SITE_TOKEN=<random-token>`; never commit that file. Install the
proxy LaunchAgent with `./ops/install_macos_site_proxy_service.sh`.

Create a named `scene2real-api` tunnel in Cloudflare, route
`scene2real-api.thecosmoslabs.com` to it, and keep its credentials under
`~/.cloudflared/`. The private config file
`~/.cloudflared/scene2real-api.yml` must route that hostname to
`http://127.0.0.1:8091`, then install the supervisor with
`./ops/install_macos_cloudflare_tunnel_service.sh`. This LaunchAgent reconnects
the tunnel after a connection drop and starts it again after login. Re-run the
backend installer after changing backend code, and the proxy installer after
changing its code or token file. `./run_local.sh` remains for development; do
not run it on a port already owned by a LaunchAgent.

## Workbench pages and G1 preview

The seven stages are separate routed views: `#video`, `#analysis`, `#targets`,
`#instruction`, `#simulation`, `#metrics`, and `#report`. The `run` query parameter preserves
run selection across refreshes and links. Previous/Continue buttons follow the
workflow; sidebar links open any stage. Instruction generation now lives on the
Instruction page. The video viewer follows the operator into Analysis and Confirm
target, so timestamp controls remain visible and usable.

The local `#report` view generates an IRS WORKSHEET after validated analysis.
It reproduces the reviewed 2012 v1.6 question index: nine sections and 158
numbered headings. It does not reconstruct all subfields, answer options or
validation rules. Every answer area has an editable suggested or example value;
the worksheet is a demonstration, not an official or validated submission.
Values can be corrected before printing, but edits stay in the browser and are
not saved to the run. There is no video evidence section. No model call or new
API route is used.

The worksheet uses one immutable run snapshot. Reset, reanalysis, reconfirmation,
run changes and evidence changes clear it. Print / Save as PDF rechecks the stored
run before opening the print dialog; unverified native printing shows a guard.
The worksheet flows across A4 pages without truncating the question set. The
historical source and its limitations are recorded in
`.prd-to-production/fire-reporting/research/`.

The Simulation page retains its recorded trajectory and adds only the simulation
branch's scene controls, observer/robot-camera selector, and articulated G1 viewer
below it. The fixed-base MuJoCo runtime, Menagerie G1 assets and local Three.js
files are selectively copied dependencies; the branch is not merged. Source asset
licensing is retained in `assets/unitree_g1/` and `static/vendor/`. This manual pose
preview does not request inference or authorize automatic spray.

Long analysis, scene/planning and simulation requests use
`POST /api/runs/{run_id}/operations` with `{"operation":"analyse"|"scene"|"run"}`.
The response is HTTP 202 with an operation ID; poll
`GET /api/runs/{run_id}/operations/{id}` for `pending`, `running`, `completed`
(with `result`) or `failed` (with `error`). `GET /api/runs/{run_id}/operations`
recovers the latest operation after a refresh. Only one operation can run per
run; duplicate starts rejoin it and server interruptions are reported as retryable.
The synchronous endpoints remain compatible. The short polling requests prevent
long model calls from holding a Cloudflare request open until it times out.

Cosmos processes views in order. Independent Astra spatial reviews overlap later
views, and the two cross-view association checks run concurrently after every view
passes. Sampling, model settings and validation are unchanged. The analysis page
separates the selected view's Cosmos and Astra times from total analysis time.
New `timings_s.analyse` values include association; `analyse_views` and
`analyse_association` record the two phases. Older multi-view timers excluded
association and are displayed as "View processing". A controlled uncached
three-view comparison improved from 78.28 s to 44.16 s; see the
[latency QA](.prd-to-production/qa/cosmos-latency.md) for measurements and limits.

## Inputs and use

1. Select one to three pinned clips, upload MP4s, or combine the two, for a single incident. Each MP4 must be 1–120 seconds and no larger than 200 MB. The team corpus has no warehouse-fire footage, so this demo uses a labelled local upload adapter. Synthetic demos are clearly labelled.
2. Analyse. Cosmos prompt `cosmos_fire_obs_v4` processes five timestamped frames per view and preserves raw responses, validated observations, scene/fire descriptions and unknowns. With spatial review enabled, Astra independently reviews the sampled frames and supplies effective fire sightings (`A1`, `A2`, …), frame-specific normalized boxes and model/prompt provenance; the original Cosmos observations remain available for audit. YOLO detections are supplementary. Each view retains its own evidence and failures; incomplete analysis blocks confirmation.
3. Review the images and evidence, group sightings of the same fire across views, exclude false positives with a reason, and choose an authored zone and slot for each physical target. Every sighting must be accounted for. Image boxes stay separate from template positions; uncalibrated metric depth is always `null`.
4. Generate the instruction and scene. Astra receives reviewed evidence and target positions, and returns a strictly validated supported plan. Run the simulation and inspect the recording, 1×/2×/4× playback and per-fire metrics.

On each page load a full-screen loader covers the workbench from first paint until the clip catalogue, warehouse zones and all seven bundled demo clips (under 1 MB in total, served read-only from `GET/HEAD /api/clips/{clip_id}/video` with range/ETag support) are downloaded and verified as MP4 bytes, and for at least three seconds. Progress shows real completed counts; slow or failed loading keeps the loader up with a Retry button and a 45-second watchdog instead of revealing an empty workbench. Verified demo bytes are kept in the browser Cache API (`scene2real-demo-clips-v1`, keyed by the catalogue's `media_sha256`) with an in-memory fallback when storage is denied, so warm reloads skip unchanged downloads; preloaded run views play from those bytes only when the run's stored `sha256` matches, while uploaded footage always streams from the run. Nothing else (uploads, run JSON, API responses) is cached.

Cross-view proposals require Astra to identify persistent shared landmarks and a supported viewpoint relationship, followed by a conservative background-feature and projective-consistency check. The system abstains when support is insufficient and leaves sightings for manual review. These proposals are not calibrated 3D reconstruction or confirmed physical-fire counts. Overlays use boxes associated with the selected sampled timestamp; a sighting without a box for that sample is hidden.

The six CCTV-style fixtures are two intended incidents with three fixed elevated views each. They use OpenAI `gpt-image-2` API-generated still imagery, locally animated, compressed and marked synthetic; they are not native AI-generated video or real CCTV footage. Independent image edits changed scene features between views, so these fixtures do not establish physical-fire correspondence or camera calibration. Generation details and hashes are recorded in [demo provenance](clips/demo_cctv_provenance.json); operator review remains necessary.

## Outputs

A run stores source clips, `run.json`, scene XML, trajectory JSON and, after a mobile simulation, `simulation.mp4` under `runs/<run_id>/`. The run records `video_refs` and the legacy first `clip_ref`, per-view raw/validated Cosmos output and status, spatial-review output and provenance, original Cosmos association suggestions for audit, selected association proposals and uncertainties, evidence warnings, reviewed `confirmed_targets` and exclusions, association and template placement provenance, instruction/model/prompt, skill, metrics, timings and telemetry. VAST archival is attempted when configured.

The authored `wh_mobile_v1` scene starts a robot at a charging station, follows a scripted aisle route, and sprays each confirmed fire. Its appearance uses published Unitree R1 dimensions and an official BSD-licensed reference URDF; the 42 referenced meshes are not bundled, and the simulator uses an authored reduced six-DOF proxy rather than the full 26-DOF robot. See [Unitree R1 reference](docs/unitree-r1.md). The station, nozzle and firefighting ability are demo additions.

The mobile success rule is computed from simulation samples: **every target receives at least 2.0 seconds of continuous valid spray exposure and there are zero unintended collisions**. Valid exposure requires aim, range and line of sight; metrics include each target's exposure, suppression time and failure reason, total targets suppressed, travel distance, duration and contacts. Walking is scripted and suppression is an exposure proxy; neither is validated fire/fluid physics. Playback can be sped up without changing the measured simulation.

## Evaluation

Run `.venv/bin/python -m pytest` for the regression suite and `node tests/frontend_evidence_check.cjs` plus `node tests/frontend_operations_check.cjs` for focused evidence, navigation dependencies and operation-polling checks. `node --test tests/test_startup_gate.mjs tests/test_boot_retry.mjs` covers the startup gate (minimum hold plus real readiness, watchdog and retry, warm-cache reuse, stale or mismatched digests, quota fallback, uploaded refs left streaming) and `tests/test_demo_media.py` covers the demo media endpoint (registered files only, traversal, range, ETag). The latest regression run passed 179 tests. Coverage includes video validation and coordinate conversion, spatial-review failures and timestamped boxes, conservative association, grouped confirmation, per-view uncertainty propagation, invalid or unavailable Astra plans, deterministic mobile motion, contact/suppression failure and MP4 export. An event-driven concurrency check verifies serial Cosmos calls, overlapping reviews and associations, input ordering and tracing context propagation.

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
