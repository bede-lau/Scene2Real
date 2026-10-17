# Scene2Real — build contract (shared by all workers)

Source of truth for product scope: `.prd-to-production/brief.md` (compact PRD v1).
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
  "prompt_id": "cosmos_fire_obs_v1",
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
