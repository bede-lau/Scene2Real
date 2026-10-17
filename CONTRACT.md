# Scene2Real — build contract (shared by all workers)

Source of truth for product scope: `.prd-to-production/brief.md` (compact PRD v2).
Runtime: Python 3.12, FastAPI, MuJoCo 3.x, runs on the team VM (`ssh bc-mattlo0546`, checkout `~/Scene2Real`,
venv `~/Scene2Real/.venv`). Secrets come from `/config/team-28.config` on the VM (sourced as env vars:
`S3_ENDPOINT ACCESS_KEY SECRET_KEY S3_CHUNKS_BUCKET S3_SEGMENTS_BUCKET GPU_BEARER_TOKEN WANDB_API_KEY
WANDB_TEAM WANDB_PROJECT`). Never write secrets into the repo or send them to the browser.

## Layout & ownership

| Path | Owner |
|---|---|
| `scene2real/scene.py`, `scene2real/sim.py`, `tests/test_sim.py` | sim worker |
| `scene2real/config.py`, `ingest.py`, `cosmos.py`, `yolo.py`, `planner.py`, `records.py`, `pipeline.py`, `app.py`, `tests/test_pipeline.py` | backend worker |
| `static/` (index.html, app.js, styles.css) | frontend worker |
| `CONTRACT.md`, `README.md`, `.prd-to-production/` | orchestrator |

## Legacy single-target contract: `wh_aisle_v1`

The following v1 sections describe the retained single-video `{fire_id, zone}` confirmation and fixed-base path. The current grouped mobile flow is specified in the v2 section below.

## World frame & warehouse template `wh_aisle_v1`

Metres. x forward (robot faces +x), y left, z up. Robot fixed base at origin, shoulder height ≈1.4 m.
Left rack row along y=+2.0, right rack row along y=-2.0, x∈[2,7]. Pallets at rack bases. Floor plane.

Authored zones (fire marker position = zone anchor):

| zone | anchor (x,y,z) | reachable |
|---|---|---|
| `left_rack` | (4.0, 1.6, 0.5) | yes |
| `right_rack` | (4.0, -1.6, 0.5) | yes |
| `aisle_center` | (4.5, 0.0, 0.3) | yes |
| `loading_dock` | (7.5, 0.0, 0.6) | yes |
| `behind_robot` | (-3.0, 0.0, 0.5) | **no** (outside torso yaw limit) — used to prove rejection |

Suggested zone from an image bbox (camera assumed looking down the aisle): bbox centre x < 0.4 → `left_rack`,
> 0.6 → `right_rack`, else `aisle_center`. Suggestion only; the user confirms. Image regions and template
metric positions are always stored separately.

## Run object (persisted at `runs/<run_id>/run.json`, archived to VAST S3 `s3://$S3_CHUNKS_BUCKET/scene2real/runs/<run_id>/`)

```json
{
  "run_id": "r_20261017_123456_ab12",
  "created_at": "iso8601",
  "state": "uploaded|analysed|needs_review|confirmed|scene_ready|blocked|completed|failed",
  "error": null | {"stage": "analyse|confirm|scene|plan|run", "message": "...", "retryable": true},
  "clip_ref": {"kind": "upload|preloaded", "filename": "...", "sha256": "...", "duration_s": 12.3,
               "local_path": "runs/<id>/clip.mp4", "s3_uri": "s3://...|null", "label": "local upload adapter (archived to VAST S3)"},
  "model_id": "nvidia/cosmos3-nano-reasoner",
  "prompt_id": "cosmos_fire_obs_v2",
  "analysis": {"raw_text": "full Cosmos response", "cached": false, "frames": [{"t_s": 0.0}], "latency_s": 4.2},
  "observations": {
    "fire_sources": [{"id": "F1", "timestamps_s": [2.0, 4.0], "bbox_normalized": [0.62,0.40,0.80,0.71],
                      "description": "burning packaging beside right rack", "suggested_zone": "right_rack"}],
    "unknowns": ["cause", "scale", "depth"],
    "cause": null, "scale": null, "depth_m": null,
    "objects": [{"label": "person", "conf": 0.8, "t_s": 2.0, "bbox_normalized": [..], "source": "yolo11"}]
  },
  "confirmed_target": {"fire_id": "F1", "zone": "right_rack", "image_bbox_normalized": [..],
                       "template_position_m": [4.0,-1.6,0.5], "position_provenance": "template-assumed (wh_aisle_v1 zone anchor)"},
  "scene": {"template_id": "wh_aisle_v1", "source_zone_mapping": {"F1": "right_rack"},
            "placements": [{"name": "fire_F1", "pos": [..], "provenance": "zone anchor right_rack, confirmed by user"}],
            "target_pos": [..], "mjcf_path": "runs/<id>/scene.xml", "settings": {"timestep": 0.002, "duration_s": 6.0}},
  "instruction": {"text": "Aim the attached extinguisher at F1", "source": "wandb|fallback",
                  "model_id": "...|null", "prompt_id": "plan_v1", "latency_s": 1.1},
  "skill": {"name": "aim_spray_demo", "target_id": "F1"},
  "metrics": {"angle_error_deg_final": 1.2, "angle_error_deg_min": 0.4, "hold_s": 3.1, "duration_s": 6.0,
              "unintended_collisions": [], "unintended_collision_count": 0, "success": true,
              "rule": "error<=5deg for >=2.0s continuous sim time AND 0 unintended collisions (attachment contacts excluded)"},
  "timings_s": {"analyse": 4.2, "scene": 0.3, "plan": 1.1, "run": 2.0},
  "telemetry": {"weave": "ok|skipped: reason", "vast": "ok|skipped: reason"}
}
```

Unobserved fields are `null`. bbox = `[x_min,y_min,x_max,y_max]`, 0–1, top-left origin.
Cosmos v2 returns native `bbox_2d` coordinates in 0–1000 per axis; validation converts these to the canonical
`bbox_normalized` field. Legacy 0–1 inputs remain supported; ambiguous coordinate formats are rejected.
`bbox_source_scale` records the declared input convention (`0-1000` or `0-1`), generated by validation;
model-supplied scale metadata cannot authorize conversion of mislabeled coordinates.
Validated sources also retain `image_center_normalized`, `location_description`, `burning_object`,
`smoke_description` and `nearby_objects`, with top-level `scene_description`. These visual details are passed
to the action planner. Metric `depth_m` is always `null` for this uncalibrated adapter. Geometry and robot
placement still come from the authored template and confirmed zone, not reconstructed visual coordinates.

## Sim module API (sim worker implements, backend calls)

```python
# scene2real/scene.py
TEMPLATE_ID = "wh_aisle_v1"
ZONES: dict[str, dict]   # {"right_rack": {"anchor": [x,y,z], "label": "Right pallet rack"}, ...}
def suggest_zone(bbox_normalized: list[float] | None) -> str | None
def build_scene(fire_sources: list[dict], mapping: dict[str, str], target_id: str) -> dict
    # fire_sources: observations.fire_sources; mapping: {fire_id: zone} (only mapped sources get markers;
    # target must be mapped). Returns {"template_id","mjcf": str,"source_zone_mapping","placements","target_pos","settings"}
    # raises ValueError on unknown zone / unmapped target.
def check_reachable(scene: dict, target_id: str) -> tuple[bool, str]

# scene2real/sim.py
SUPPORTED_SKILLS = {"aim_spray_demo"}
def simulate(scene: dict, skill: dict) -> tuple[dict, dict]
    # skill = {"name": "aim_spray_demo", "target_id": "F1"}; raises ValueError for unsupported skill/target.
    # Returns (metrics, trajectory). Deterministic: same scene → same result (replay).
```

Trajectory (served at `GET /api/runs/{id}/trajectory`, consumed by three.js):

```json
{"fps": 30, "duration_s": 6.0,
 "geoms": [{"name": "rack_L1_post0", "type": "box|sphere|capsule|cylinder|plane", "size": [..mujoco half-sizes..], "rgba": [r,g,b,a], "group": "env|robot|extinguisher|fire"}],
 "frames": [[x,y,z,qw,qx,qy,qz, ... one 7-tuple per geom in geoms order ...], ...],
 "fx": {"fires": [{"id": "F1", "pos": [..], "target": true}], "spray": [{"frame": 40, "on": true}],
        "nozzle": [[x,y,z,dx,dy,dz] per frame]},
 "angle_error_deg": [per frame]}
```
Robot: fixed-base simple humanoid (torso, head, 2 arms, legs as static visual), torso yaw + right shoulder
pitch/yaw + elbow hinge driven by position actuators to scripted joint targets/keyframes; extinguisher
body welded/attached to right hand (nozzle site at its tip). Fire and spray are visual only.

## HTTP API (`scene2real/app.py`, serves `static/` at `/`)

| Method | Path | Body | Result |
|---|---|---|---|
| GET | `/api/clips` | | `[{"clip_id","label","filename","duration_s"}]` (pinned demo clip(s) in `clips/`) |
| GET | `/api/zones` | | `{zone: {"anchor","label","reachable"}}` |
| POST | `/api/runs` | multipart `file` (mp4, ≤200 MB) **or** JSON `{"clip_id"}` | run object (state `uploaded`) |
| GET | `/api/runs/{id}` | | run object |
| GET | `/api/runs/{id}/video` | | mp4 |
| POST | `/api/runs/{id}/analyse` | | run (`analysed` or `needs_review`/`failed` + error) |
| POST | `/api/runs/{id}/confirm` | `{"fire_id","zone"}` | run (`confirmed`, or 422 with message) |
| POST | `/api/runs/{id}/scene` | | builds scene + instruction/plan; run (`scene_ready` or `blocked`) |
| POST | `/api/runs/{id}/run` | | simulate; run (`completed`) |
| POST | `/api/runs/{id}/reset` | | clears metrics/trajectory, keeps scene → `scene_ready` |
| GET | `/api/runs/{id}/trajectory` | | trajectory JSON |

Errors: HTTP 4xx/5xx with `{"detail": "...", "retryable": bool}`; run.error also set. Upstream service
failure (Cosmos, W&B) → `failed`/retryable so the UI shows Retry. Stage gating enforced server-side (409 if
the action isn't valid in the current state).


## Multi-view and mobile contract (v2)

The current workbench uses grouped confirmation even with one input video. `POST /api/runs` accepts JSON `{"clip_ids":["id1","id2"]}` or multipart repeated `files` plus an optional `clip_ids` field containing a JSON array. The combined input must contain one to three valid MP4s. Legacy JSON `{"clip_id":"id"}` and multipart `file` remain supported. `video_refs` identify views `V1` through `V3`, and `clip_ref` aliases the first. `GET /api/runs/{id}/video/{view_id}` serves a selected view; `/video` retains the first-view behavior. `GET /api/zones` adds mobile `slots` to the legacy zone data.

`POST /api/runs/{id}/analyse` samples five timestamped frames per view with Cosmos `cosmos_fire_obs_v4` and retains each view's raw response under `analysis.views`. When spatial review is enabled, Astra independently reviews the frames with `astra_fire_grounding_v1`. Effective sightings receive IDs such as `A1` (aggregated as `V1:A1` for multi-view runs), normalized `bbox_by_frame` entries with timestamps, a reference `bbox_normalized` and `bbox_at_s`, and `bbox_provenance`. The original validated Cosmos observations remain in each view's `analysis.spatial_review.original_observations`, alongside review status, model, prompt and response. Image overlays use the selected sampled timestamp and hide a sighting when it has no box at that sample. `SCENE2REAL_SPATIAL_REVIEW=auto` enables the review when `OPENAI_API_KEY` exists; `1` requires the review and `0` uses unreviewed legacy Cosmos boxes. An unavailable or invalid enabled review fails or requires review rather than silently falling back.

For a multi-view run, original Cosmos association suggestions are retained under `analysis.cosmos_association` for audit. `analysis.association` records Astra `astra_fire_association_v1` proposals, actual model, prompt, response, timing, evidence, uncertainties and errors. Only boxes at the selected frame's exact timestamp enter matching. Candidates require evidence of persistent shared landmarks and viewpoint orientation, plus a conservative SIFT/RANSAC background homography and projected fire-base consistency check. This planar check is not a calibrated 3D reconstruction. Unsupported or contradictory camera identity, missing eligible sightings, or an unavailable association pass results in manual review without automatic candidates; an operator can still group or exclude sightings. Candidates are proposals, never confirmed physical-fire counts. Incomplete per-view analysis prevents confirmation; a view with no fires is permitted when the incident has fire evidence elsewhere. Normalized image regions are not metric positions and uncalibrated `depth_m` remains null.

Grouped confirmation body example:

```json
{
  "targets": [
    {"members": ["V1:A1", "V2:A2"], "zone": "left_rack", "slot": 0},
    {"members": ["V1:A2"], "zone": "aisle_center", "slot": 1}
  ],
  "excluded": [{"id": "V2:A1", "reason": "duplicate reflection"}]
}
```

Each sighting must appear exactly once in a group or reasoned exclusion; each group has at most one sighting from a view. One to twelve targets are supported, each with a distinct reachable zone/slot. The server assigns `T1`, `T2`, etc., and records `confirmed_targets` with members, image evidence, association provenance, authored `template_position_m` and its provenance. Association provenance distinguishes single-view sightings, operator-confirmed supported proposals and operator-authored unverified groups. The legacy `{fire_id, zone}` confirmation is restricted to a single view.

For a grouped confirmation, `/scene` calls the real OpenAI Responses API with `gpt-6-astra` and prompt `mobile_plan_r1_v2`. It passes only reviewed target evidence, records actual model and prompt provenance, and validates an exact structured response: `instruction`, skill `mobile_suppress_demo` with every confirmed target exactly once, and settings `wh_mobile_v1`, `aisle_safe`, `water_demo`, walking speed 0.25–1.0 m/s and spray duration 3–8 s. No arbitrary code or geometry is accepted. A missing credential or provider failure is reported for retry; no fallback plan is substituted in this flow.

The authored mobile scene includes a charging station, warehouse, fire targets and a scripted six-DOF robot proxy. It is visually informed by the official BSD-licensed Unitree R1 URDF and product dimensions, but does not load its absent meshes or simulate its full 26 joints. See [Unitree reference](docs/unitree-r1.md). `POST /api/runs/{id}/run` produces trajectory and an MP4 at `GET /api/runs/{id}/simulation-video`. Metrics report each target's valid continuous exposure, suppression time and failures, travel, duration and unintended contacts. Success requires at least two continuous seconds of valid spray exposure for **every** target and zero unintended collisions; this is a simulation proxy, not fire or fluid physics. `reset` clears the outcome and recording while retaining the plan for repeat runs.

The synthetic CCTV fixtures use independently API-generated `gpt-image-2` stills with local animation and compression, not native generated video. Independent edits changed scene features between intended camera views, so they do not establish calibration or physical-fire correspondence. Operator review is required.
