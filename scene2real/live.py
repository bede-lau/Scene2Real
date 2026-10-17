"""Authoritative live MuJoCo state and camera-only Cosmos decisions.

This is a perception-driven prototype: named, authored motions are executed by
bounded MuJoCo actuators; suppression is a simplified ray/exposure model.
"""
from __future__ import annotations

import base64
import hashlib
import json
import math
import re
import threading
import time
import uuid
from collections import deque
from pathlib import Path

import mujoco
import numpy as np
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse

from . import config, cosmos
from . import live_model

router = APIRouter(prefix="/api/live", tags=["live simulation"])
SESSIONS: dict[str, "LiveSession"] = {}
SESSIONS_LOCK = threading.Lock()
MAX_SESSIONS = 4
DECISION_LEASE_S = 24.0
MAX_SNAPSHOT_AGE_S = 10.0
MAX_RESPONSE_AGE_S = max(240.0, config.COSMOS_TIMEOUT_S + 10)


def cosmos_enabled():
    return config.get("SCENE2REAL_LIVE_COSMOS", "0") == "1"


def _quat(matrix):
    q = np.zeros(4)
    mujoco.mju_mat2Quat(q, np.asarray(matrix).flatten())
    return q.tolist()


def _write_json(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False))


def _reports_uncertainty(obj):
    """Fail closed on explicit global or per-source uncertainty extensions.

    The existing observation schema has no calibrated confidence score. Missing
    scores do not imply certainty; explicit uncertainty must never be ignored.
    """
    if obj.get("uncertain"):
        return True
    if "confidence" in obj:
        confidence = obj["confidence"]
        if isinstance(confidence, bool) or not isinstance(confidence, (int, float)) or not math.isfinite(confidence) or not .55 <= confidence <= 1:
            return True
    unknowns = obj.get("unknowns", [])
    if isinstance(unknowns, list) and any(any(word in str(u).lower() for word in ("fire", "visibility", "location")) for u in unknowns):
        return True
    return bool(re.search(r"\b(possible|possibly|uncertain|unconfirmed|cannot confirm|might be|may be)\b", str(obj.get("description", "")), re.I))


class LiveSession:
    def __init__(self, start_thread=True):
        self.id = uuid.uuid4().hex[:12]
        self.model = live_model.get_model()
        self.data = live_model.create_data(self.model)
        self.presets = live_model.build_presets(self.model)
        self.lock = threading.RLock()
        self.directory = config.RUNS_DIR / ("live_" + self.id)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.revision = 0
        self.seq = 0
        self.scenario = "center"
        self.paused = False
        self.closed = False
        self.intensity = 1.0
        self.pose = "center"
        self.request_generation = 0
        self.decision = {"status": "idle", "detail": "Capture the robot camera and run Cosmos to authorize spray."}
        self.lease_until = 0.0
        self.spray = {"on": False, "hit": False, "blocked": False, "point": None}
        self.metrics = {"hit_s": 0.0, "miss_s": 0.0, "blocked_s": 0.0}
        self.events = deque(maxlen=2000)
        self.snapshots = deque(maxlen=600)
        self.inferences = []
        self.trace_at = 0.0
        self.last_active = time.monotonic()
        self.nozzle_id = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_SITE, "live_nozzle")
        self.camera_id = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_CAMERA, "live_camera")
        self.fire_geom = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_GEOM, "live_fire")
        self.occluder_geom = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_GEOM, "live_occluder")
        self.fire_mocap = int(self.model.body_mocapid[mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_BODY, "live_fire_body")])
        self.obstacle_mocap = int(self.model.body_mocapid[mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_BODY, "live_occluder_body")])
        self.actuator_joint_ids = np.asarray(self.model.actuator_trnid[:, 0], dtype=int)
        self.actuator_qpos = self.model.jnt_qposadr[self.actuator_joint_ids]
        self.reference = self.data.qpos[self.actuator_qpos].copy()
        self.target = self.reference.copy()
        self.transition_start = self.reference.copy()
        self.transition_elapsed = 0.0
        self.transition_duration = 1.0
        self._set_pose("center")
        self.set_scene({"scenario": "center"})
        _write_json(self.directory / "provenance.json", {
            "description": "Perception-driven animated prototype with predefined motions and simplified ray-based suppression physics.",
            "engine": "MuJoCo", "timestep_s": float(self.model.opt.timestep),
            "policy": "Predefined left/center/right arm references; not a trained robot policy.",
            "model": cosmos.MODEL_ID, "prompt_id": cosmos.PROMPT_ID,
            "suppression_rate_per_sim_s": 0.24,
        })
        if start_thread:
            threading.Thread(target=self._loop, name="mujoco-" + self.id, daemon=True).start()

    def _event(self, kind, **fields):
        value = {"kind": kind, "wall_time": time.time(), "sim_time": float(self.data.time),
                 "scene_revision": self.revision, **fields}
        self.events.append(value)
        with (self.directory / "events.jsonl").open("a") as f:
            f.write(json.dumps(value, allow_nan=False) + "\n")

    def _set_pose(self, pose):
        if pose not in self.presets:
            raise ValueError("pose must be left, center, or right")
        self.pose = pose
        preset = self.presets[pose]
        if isinstance(preset, dict):
            for a, jid in enumerate(self.actuator_joint_ids):
                name = mujoco.mj_id2name(self.model, mujoco.mjtObj.mjOBJ_JOINT, int(jid))
                if name in preset:
                    self.target[a] = float(preset[name])
        else:
            self.target[:] = np.asarray(preset)[self.actuator_qpos]
        for a, jid in enumerate(self.actuator_joint_ids):
            if self.model.jnt_limited[jid]:
                self.target[a] = np.clip(self.target[a], *self.model.jnt_range[jid])
        self.target[:] = np.clip(self.target, self.model.actuator_ctrlrange[:, 0], self.model.actuator_ctrlrange[:, 1])
        self.transition_start = self.reference.copy()
        self.transition_elapsed = 0.0
        # Quintic blend has zero velocity/acceleration at either endpoint. Scale
        # duration so max blend speed never exceeds 0.85 radians/s.
        self.transition_duration = max(.8, 1.875 * float(np.max(np.abs(self.target - self.reference))) / .85)

    def _revoke(self, status="idle", detail="Spray permission revoked"):
        self.lease_until = 0
        self.spray.update(on=False, hit=False, blocked=False)
        self.decision = {"status": status, "detail": detail}

    def set_scene(self, body):
        scenario = body.get("scenario", self.scenario)
        if scenario not in {"left", "center", "right", "none", "obscured", "wrong"}:
            raise ValueError("invalid scenario")
        anchor = scenario if scenario in {"left", "center", "right"} else "center"
        position = np.array(live_model.TARGETS[anchor], dtype=float)
        if body.get("fire_y") is not None:
            if isinstance(body["fire_y"], bool):
                raise ValueError("fire_y must be a number")
            y = float(body["fire_y"])
            if not math.isfinite(y) or abs(y) > 1.2:
                raise ValueError("fire_y must be finite and within +/-1.2 m")
            position[1] = y
        if "obstacle" in body and not isinstance(body["obstacle"], bool):
            raise ValueError("obstacle must be a boolean")
        obstacle = body.get("obstacle", scenario == "obscured" if "scenario" in body else getattr(self, "obstacle", False))
        with self.lock:
            self.last_active = time.monotonic()
            self.revision += 1
            self.scenario = scenario
            self.request_generation += 1
            self._revoke("idle", "Scene changed; capture a fresh robot-camera image.")
            self.intensity = 0.0 if scenario == "none" else 1.0
            self.data.mocap_pos[self.fire_mocap] = position if self.intensity else [0, 0, -20]
            self.obstacle = obstacle
            self.data.mocap_pos[self.obstacle_mocap] = [1.4, position[1] * .5, 1.05] if self.obstacle else [0, 0, -20]
            self.metrics = {"hit_s": 0.0, "miss_s": 0.0, "blocked_s": 0.0}
            self._set_pose("center")
            mujoco.mj_forward(self.model, self.data)
            self._event("scene", scenario=scenario, fire_position=position.tolist(), obstacle=self.obstacle)
            return self.state()

    def _camera(self):
        return {"position": self.data.cam_xpos[self.camera_id].tolist(),
                "quaternion": _quat(self.data.cam_xmat[self.camera_id]),
                "fovy": float(self.model.cam_fovy[self.camera_id]), "name": "live_camera"}

    def state(self):
        with self.lock:
            self.last_active = time.monotonic()
            self.seq += 1
            cam = self._camera()
            self.snapshots.append({"seq": self.seq, "at": time.monotonic(), "revision": self.revision, "camera": cam})
            poses = [np.r_[self.data.geom_xpos[g], _quat(self.data.geom_xmat[g])].tolist() for g in range(self.model.ngeom)]
            nozzle = np.r_[self.data.site_xpos[self.nozzle_id], self.data.site_xmat[self.nozzle_id].reshape(3, 3)[:, 2]].tolist()
            error = float(np.max(np.abs(self.data.qpos[self.actuator_qpos] - self.target)))
            self._aim_error()
            return {"session_id": self.id, "scene_revision": self.revision, "seq": self.seq,
                    "sim_time": float(self.data.time), "paused": self.paused, "scenario": self.scenario, "obstacle": self.obstacle,
                    "geoms": poses, "nozzle": nozzle, "camera": cam,
                    "fire": {"position": self.data.mocap_pos[self.fire_mocap].tolist(), "intensity": self.intensity},
                    "decision": dict(self.decision), "spray": dict(self.spray), "pose": self.pose,
                    "metrics": {**self.metrics, "tracking_error_rad": error, "contacts": int(self.data.ncon)},
                    "joints": {"actual": self.data.qpos[self.actuator_qpos].tolist(), "reference": self.reference.tolist(),
                               "target": self.target.tolist(), "actuator_force": self.data.actuator_force.tolist()},
                    "evidence_url": f"/api/live/{self.id}/evidence",
                    "policy": "Predefined arm poses; not a trained robot policy", "physics": "MuJoCo; simplified hit-based suppression"}

    def step(self, count=10):
        dt = float(self.model.opt.timestep)
        for _ in range(count):
            if self.paused:
                return
            # Smooth bounded reference, never overwrite actual joint positions.
            self.transition_elapsed += dt
            u = min(1.0, self.transition_elapsed / self.transition_duration)
            blend = 10 * u**3 - 15 * u**4 + 6 * u**5
            self.reference[:] = self.transition_start + blend * (self.target - self.transition_start)
            self.data.ctrl[:] = self.reference
            mujoco.mj_step(self.model, self.data)
            # mj_step integrates qpos after computing derived geometry. Refresh
            # so camera, rendered bodies and ray all describe that same qpos.
            mujoco.mj_forward(self.model, self.data)
            self._suppression(dt)
        if self.data.time - self.trace_at >= .2:
            self.trace_at = float(self.data.time)
            self._event("physics", intensity=self.intensity, pose=self.pose, spray=dict(self.spray),
                        actual=self.data.qpos[self.actuator_qpos].tolist(), reference=self.reference.tolist(),
                        actuator_force=self.data.actuator_force.tolist(), contacts=int(self.data.ncon))

    def _suppression(self, dt):
        if self.decision.get("status") == "ready" and time.monotonic() > self.lease_until:
            self._revoke("stale", "Decision lease expired; capture another camera image.")
        actual_error = float(np.max(np.abs(self.data.qpos[self.actuator_qpos] - self.target)))
        motion_complete = self.transition_elapsed >= self.transition_duration
        enabled = self.decision.get("status") == "ready" and time.monotonic() < self.lease_until and motion_complete and actual_error < .14 and self.intensity > 0
        self.spray = {"on": bool(enabled), "hit": False, "blocked": False, "point": None}
        if not enabled:
            return
        origin = self.data.site_xpos[self.nozzle_id].copy()
        direction = self.data.site_xmat[self.nozzle_id].reshape(3, 3)[:, 2].copy()
        direction /= np.linalg.norm(direction)
        # Include environment and robot collision geometry. Exclude only visual
        # meshes and the tool body containing the ray origin.
        groups = np.ones(6, dtype=np.uint8)
        groups[2] = 0
        gid = np.array([-1], dtype=np.int32)
        tool_body = int(self.model.site_bodyid[self.nozzle_id])
        distance = float(mujoco.mj_ray(self.model, self.data, origin, direction, groups, 1, tool_body, gid))
        within = distance >= 0 and distance <= 6.0
        hit = within and int(gid[0]) == self.fire_geom
        blocked = within and int(gid[0]) != self.fire_geom
        endpoint = origin + direction * (distance if within else 6.0)
        self.spray.update(hit=bool(hit), blocked=bool(blocked), distance=distance if within else 6.0,
                          point=endpoint.tolist(), geom_id=int(gid[0]))
        self.metrics["hit_s" if hit else "miss_s"] += dt
        if blocked:
            self.metrics["blocked_s"] += dt
        if hit:
            self.intensity = max(0.0, self.intensity - .24 * dt)
            if self.intensity <= 0:
                self._event("extinguished", snapshot_id=self.decision.get("snapshot_id"))
                self._revoke("no_fire", "Fire extinguished by actual unobstructed nozzle-ray exposure.")
        self._aim_error()

    def _aim_error(self):
        if self.intensity <= 0:
            self.metrics["angle_error_deg"] = None
            return
        origin = self.data.site_xpos[self.nozzle_id]
        direction = self.data.site_xmat[self.nozzle_id].reshape(3, 3)[:, 2]
        target = self.data.geom_xpos[self.fire_geom] - origin
        if np.linalg.norm(target) > 1e-6:
            self.metrics["angle_error_deg"] = math.degrees(math.acos(float(np.clip(direction @ target / np.linalg.norm(target), -1, 1))))

    def _loop(self):
        while not self.closed:
            start = time.monotonic()
            with self.lock:
                if start - self.last_active > 1800:
                    self.closed = True
                    return
                try:
                    self.step()
                except Exception as e:
                    self.paused = True
                    self.request_generation += 1
                    self._revoke("failed", f"Physics stopped safely: {type(e).__name__}. Reset or restart the local session.")
            time.sleep(max(.001, .02 - (time.monotonic() - start)))

    def submit(self, body):
        return self.capture_snapshot(body, infer=True)

    def capture_snapshot(self, body, infer=False):
        """Save the same validated robot-camera evidence with optional inference.

        A valid capture alone never grants, revokes, or renews spray permission.
        """
        if infer and not cosmos_enabled():
            with self.lock:
                self._revoke("disabled", "Cosmos is disabled for this local preview. Predefined poses remain available.")
            raise HTTPException(503, "Cosmos is disabled for this local preview")
        image = body.get("image", "")
        if not isinstance(image, str) or not image.startswith("data:image/jpeg;base64,") or len(image) > 7_000_000:
            raise ValueError("image must be a robot-camera JPEG data URL, at most 5 MB")
        try:
            raw = base64.b64decode(image.split(",", 1)[1], validate=True)
        except Exception as e:
            raise ValueError("invalid JPEG base64") from e
        if not raw.startswith(b"\xff\xd8") or len(raw) < 100:
            raise ValueError("invalid JPEG image")
        snapshot_id = body.get("snapshot_id")
        if not isinstance(snapshot_id, str) or not (1 <= len(snapshot_id) <= 100):
            raise ValueError("snapshot_id required")
        with self.lock:
            if infer and self.decision.get("status") == "pending":
                raise HTTPException(409, "Cosmos inference already pending; scene edits invalidate its result")
            source = next((s for s in reversed(self.snapshots) if s["seq"] == body.get("state_seq")), None)
            if source is None or body.get("scene_revision") != self.revision or source["revision"] != self.revision or time.monotonic() - source["at"] > MAX_SNAPSHOT_AGE_S:
                self._revoke("stale", "Snapshot is stale; capture the current robot camera.")
                raise HTTPException(409, "Snapshot state sequence/revision is stale")
            supplied = body.get("camera_pose")
            if not isinstance(supplied, dict):
                raise ValueError("camera_pose with position and quaternion is required")
            try:
                pos = np.asarray(supplied["position"], dtype=float)
                quat = np.asarray(supplied["quaternion"], dtype=float)
                valid = pos.shape == (3,) and quat.shape == (4,) and np.all(np.isfinite(pos)) and np.all(np.isfinite(quat)) and abs(float(np.linalg.norm(quat)) - 1) < .002 and np.linalg.norm(pos - source["camera"]["position"]) < .01 and abs(abs(float(quat @ np.asarray(source["camera"]["quaternion"]))) - 1) < .002
            except (KeyError, TypeError, ValueError):
                valid = False
            if not valid:
                self._revoke("stale", "Camera metadata does not match the robot-camera snapshot.")
                raise HTTPException(409, "Camera metadata does not match the authoritative robot camera")
            revision = self.revision
            unique = uuid.uuid4().hex[:10]
            path = self.directory / f"camera_{unique}.jpg"
            path.write_bytes(raw)
            record = {"snapshot_id": snapshot_id, "scene_revision": revision, "state_seq": source["seq"],
                      "camera_pose": source["camera"], "image_sha256": hashlib.sha256(raw).hexdigest(),
                      "image_file": path.name, "scenario": self.scenario, "model": cosmos.MODEL_ID,
                      "prompt_id": cosmos.PROMPT_ID, "submitted_at": time.time(), "source": "robot_camera",
                      "inference_requested": infer}
            _write_json(self.directory / (path.stem + "_snapshot.json"), record)
            self._event("snapshot", **record)
            if infer:
                self.request_generation += 1
                generation = self.request_generation
                self._revoke("pending", "Cosmos is analysing the saved robot-camera image; spray is off.")
                self.decision.update(snapshot_id=snapshot_id, source_snapshot=record)
                threading.Thread(target=self._infer, args=(record, path, generation, revision), daemon=True).start()
            result = self.state()
            result["saved_snapshot"] = {**record, "image_url": f"/api/live/{self.id}/evidence/{path.name}"}
            return result

    def _infer(self, record, path, generation, revision):
        start = time.monotonic()
        raw, obs, status, detail, pose = "", None, "failed", "Cosmos inference failed", None
        try:
            # Deliberately bypass cache: acceptance evidence must be actual inference.
            raw = cosmos.call_cosmos([{"path": str(path), "t_s": 0.0}])
            obj = cosmos.extract_json(raw)
            try:
                json.dumps(obj, allow_nan=False)
            except ValueError as e:
                raise cosmos.InvalidOutput("Cosmos output contains non-finite numbers", raw) from e
            if _reports_uncertainty(obj):
                status, detail = "uncertain", "Cosmos reported uncertainty; spray inhibited."
            elif obj.get("fire_sources") == []:
                status, detail = "no_fire", "Cosmos reported no visible fire; spray inhibited."
                obs = {"fire_sources": [], "scene_description": obj.get("scene_description"), "unknowns": obj.get("unknowns", [])}
            else:
                obs = cosmos.validate(obj, 0.0, raw)
                if len(obs["fire_sources"]) != 1 or any(_reports_uncertainty(source) for source in obj["fire_sources"]):
                    status, detail = "uncertain", "Ambiguous fire evidence; spray inhibited."
                else:
                    cx = obs["fire_sources"][0]["image_center_normalized"][0]
                    pose = "left" if cx < .4 else "right" if cx > .6 else "center"
                    status, detail = "ready", f"Visible fire mapped to predefined {pose} pose."
        except cosmos.InvalidOutput as e:
            status, detail = "invalid", str(e)
            raw = getattr(e, "raw_text", raw) or raw
        except Exception as e:
            status, detail = "failed", f"Cosmos unavailable: {type(e).__name__}. No simulated decision substituted."
        latency = time.monotonic() - start
        with self.lock:
            current_cam = self._camera()
            source_cam = record["camera_pose"]
            moved = np.linalg.norm(np.asarray(current_cam["position"]) - source_cam["position"]) > .03 or abs(float(np.asarray(current_cam["quaternion"]) @ source_cam["quaternion"])) < .999
            stale = self.closed or generation != self.request_generation or revision != self.revision or latency > MAX_RESPONSE_AGE_S or moved
            entry = {**record, "latency_s": round(latency, 3), "raw_text": raw, "observations": obs,
                     "status": "stale" if stale else status, "proposed_pose": pose, "detail": detail,
                     "completed_at": time.time(), "cached": False}
            self.inferences.append(entry)
            _write_json(self.directory / (path.stem + "_response.json"), entry)
            self._event("inference", **entry)
            if stale:
                # Do not overwrite a newer request's result or authorize old evidence.
                if generation == self.request_generation:
                    self._revoke("stale", "Camera/scene changed or response expired; old decision discarded.")
                return
            self._revoke(status, detail)
            self.decision.update(snapshot_id=record["snapshot_id"], source_snapshot=record, latency_s=round(latency, 3),
                                 raw_text=raw, observations=obs, pose=pose, cached=False)
            if status == "ready":
                applied = ("left" if pose != "left" else "right") if self.scenario == "wrong" else pose
                self._set_pose(applied)
                self.decision.update(applied_pose=applied, predefined=True)
                self.lease_until = time.monotonic() + DECISION_LEASE_S
                if self.scenario == "wrong":
                    self.decision["detail"] += " Deliberate wrong-aim override applied to prove hit-dependent suppression."

    def control(self, body):
        with self.lock:
            action = body.get("action")
            if action in {"pause", "stop"}:
                if action == "pause":
                    self.paused = True
                self.request_generation += 1
                self._revoke("idle", "Operator stopped spray; fresh inference required.")
            elif action == "resume":
                self.paused = False
            elif action == "pose":
                self._set_pose(body.get("pose"))
                self.request_generation += 1
                self._revoke("idle", "Manual predefined pose preview; fresh camera inference required for spray.")
                self._event("manual_pose", pose=self.pose, spray_authorized=False)
            elif action == "reset":
                self.paused = False
                return self.set_scene({"scenario": self.scenario})
            else:
                raise ValueError("action must be pause, resume, stop, reset, or pose")
            return self.state()

    def evidence(self):
        with self.lock:
            result = {"session_id": self.id, "state": self.state(), "inferences": list(self.inferences),
                      "events": list(self.events), "files": [{"name": p.name, "url": f"/api/live/{self.id}/evidence/{p.name}"} for p in sorted(self.directory.iterdir()) if p.is_file()],
                      "description": "Actual Cosmos responses are marked cached=false. Missing credentials are failures, never synthetic successes."}
            _write_json(self.directory / "evidence.json", result)
            return result


def get_session(session_id):
    with SESSIONS_LOCK:
        session = SESSIONS.get(session_id)
    if session is None or session.closed:
        raise HTTPException(404, "Live session not found; create another session")
    return session


def evidence_directory(session_id):
    """Resolve archived evidence without restoring or starting a simulation."""
    if not re.fullmatch(r"[0-9a-f]{12}", session_id):
        raise HTTPException(400, "Invalid live session ID")
    directory = config.RUNS_DIR / ("live_" + session_id)
    if not directory.is_dir():
        raise HTTPException(404, "Live evidence not found")
    return directory


@router.get("/config")
def live_config():
    try:
        model = live_model.get_model()
        available, detail = True, f"{model.nq} coordinates / {model.nu} bounded actuators"
    except Exception as e:
        available, detail = False, f"{type(e).__name__}: {e}"
    return {"model_available": available, "detail": detail, "cosmos_configured": cosmos_enabled() and bool(config.get("GPU_BEARER_TOKEN")),
            "cosmos_enabled": cosmos_enabled(),
            "model": cosmos.MODEL_ID, "prompt_id": cosmos.PROMPT_ID, "weave": config.TELEMETRY["weave"]}


@router.get("/model")
def model_manifest():
    return live_model.manifest(live_model.get_model())


@router.post("")
def create_session():
    with SESSIONS_LOCK:
        if len(SESSIONS) >= MAX_SESSIONS:
            oldest = min(SESSIONS.values(), key=lambda s: s.last_active)
            oldest.closed = True
            del SESSIONS[oldest.id]
        session = LiveSession()
        SESSIONS[session.id] = session
    return session.state()


@router.get("/{session_id}")
def session_state(session_id: str):
    return get_session(session_id).state()


@router.post("/{session_id}/scene")
async def set_scene(session_id: str, request: Request):
    try:
        return get_session(session_id).set_scene(await request.json())
    except (ValueError, TypeError, AttributeError) as e:
        raise HTTPException(422, str(e)) from e


@router.post("/{session_id}/analyse")
async def analyse(session_id: str, request: Request):
    session = get_session(session_id)
    try:
        return session.submit(await request.json())
    except (ValueError, TypeError, AttributeError) as e:
        with session.lock:
            session.request_generation += 1
            session._revoke("invalid", "Invalid camera request; spray inhibited.")
        raise HTTPException(422, str(e)) from e


@router.post("/{session_id}/snapshot")
async def capture_snapshot(session_id: str, request: Request):
    session = get_session(session_id)
    try:
        return session.capture_snapshot(await request.json())
    except (ValueError, TypeError, AttributeError) as e:
        with session.lock:
            session.request_generation += 1
            session._revoke("invalid", "Invalid camera snapshot; spray inhibited.")
        raise HTTPException(422, str(e)) from e


@router.post("/{session_id}/control")
async def control(session_id: str, request: Request):
    try:
        return get_session(session_id).control(await request.json())
    except (ValueError, TypeError, AttributeError) as e:
        raise HTTPException(422, str(e)) from e


@router.get("/{session_id}/evidence")
def evidence(session_id: str):
    directory = evidence_directory(session_id)
    with SESSIONS_LOCK:
        session = SESSIONS.get(session_id)
    if session is not None and not session.closed:
        return session.evidence()
    saved = directory / "evidence.json"
    if saved.is_file():
        result = json.loads(saved.read_text())
    else:
        events_file = directory / "events.jsonl"
        events = deque(maxlen=2000)
        if events_file.is_file():
            with events_file.open() as stream:
                for line in stream:
                    try:
                        events.append(json.loads(line))
                    except ValueError:
                        continue  # Ignore a last partial append after interruption.
        provenance = directory / "provenance.json"
        result = {"session_id": session_id, "events": list(events),
                  "provenance": json.loads(provenance.read_text()) if provenance.is_file() else {},
                  "inferences": [json.loads(p.read_text()) for p in sorted(directory.glob("*_response.json"))]}
    result.update(archived=True, live=False, state_is_historical="state" in result,
                  files=[{"name": p.name, "url": f"/api/live/{session_id}/evidence/{p.name}"}
                         for p in sorted(directory.iterdir()) if p.is_file()])
    return result


@router.get("/{session_id}/evidence/{filename}")
def evidence_file(session_id: str, filename: str):
    directory = evidence_directory(session_id)
    if Path(filename).name != filename or filename in {".", ".."}:
        raise HTTPException(400, "Invalid filename")
    path = directory / filename
    if not path.is_file():
        raise HTTPException(404, "Evidence file not found")
    return FileResponse(path)


@router.post("/{session_id}/recording")
async def save_recording(session_id: str, request: Request):
    session = get_session(session_id)
    limit = 100 * 1024 * 1024
    raw = bytearray()
    async for chunk in request.stream():
        if len(raw) + len(chunk) > limit:
            raise HTTPException(413, "Recording must be nonempty and under 100 MB")
        raw.extend(chunk)
    if not raw:
        raise HTTPException(413, "Recording must be nonempty and under 100 MB")
    if not raw.startswith(b"\x1aE\xdf\xa3"):
        raise HTTPException(422, "Expected WebM recording")
    name = "recording_" + uuid.uuid4().hex[:8] + ".webm"
    (session.directory / name).write_bytes(raw)
    with session.lock:
        session._event("recording", file=name, bytes=len(raw))
        session.evidence()  # Preserve the final recording event/state across restart.
    return {"url": f"/api/live/{session.id}/evidence/{name}", "bytes": len(raw)}
