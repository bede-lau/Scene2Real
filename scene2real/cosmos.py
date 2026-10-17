"""Cosmos-Reason (CoreWeave) fire observation: frames -> strict JSON -> validated observations."""
import base64
import json
import math
import re
import time

import requests

from . import config

PROMPT_ID = "cosmos_fire_obs_v4"
MODEL_ID = config.COSMOS_MODEL

PROMPT = """You are analysing frames sampled in time order from a short video of a warehouse. Look for visible fire sources.
Respond with ONLY one JSON object (no markdown fences, no commentary after it) with exactly this schema:
{"scene_description":"<visible warehouse layout and objects>",
 "fire_sources":[{"id":"F1","timestamps_s":[<frame times where visible>],"bbox_2d":[x_min,y_min,x_max,y_max],
 "description":"<visible fire evidence>","location_description":"<image-relative position and relation to nearby objects>",
 "burning_object":<visible burning object or null>,"smoke_description":<visible smoke color, direction and occlusion or null>,
 "nearby_objects":[<visible objects near this fire>]}],
 "cause":<string or null>,"scale":<string or null>,"depth_m":<number or null>,"unknowns":[<names of fields you could not determine>]}
Rules: ids are F1, F2, ... unique. Use Cosmos native bbox_2d coordinates normalized to 0-1000 independently on each axis,
origin top-left, x_min<x_max, y_min<y_max. Example: [550,200,700,650]. Enclose the visible flames and burning object,
not the entire smoke plume. Do not use pixel coordinates or a key named bbox_normalized.
timestamps_s must come from the frame times given. Describe only visible evidence: position in the image (left/right,
foreground/background), floor or shelf placement, adjacent racks/pallets/boxes, smoke and visibility.
Count distinct physical burning sites across the entire sampled sequence, not individual flame tongues or frame appearances.
Inspect every frame, including small or partially occluded areas. Group flames arising from the same localized burning object
or continuous burning area; keep spatially distinct burning objects or pallet fires separate. Track each source across
frames using nearby objects and scene context, allowing for camera motion, occlusion and changing flame shape. Reuse its ID
and collect its visible timestamps rather than creating another entry when it reappears. Do not count reflections, glare,
glow or smoke alone as additional sources. Check that each entry identifies a distinct burning site with its own box.
Do not assume a source count. If identity, separation, or whether something is actual fire remains unresolved, describe
that uncertainty in the relevant descriptions and unknowns rather than asserting an unsupported distinction or merger.
No camera calibration, measured scale or depth sensor is provided: depth_m MUST be null and depth MUST be in unknowns.
Do not infer distances, metric sizes, unseen layout, a robot's pose, or the cause of ignition. Cause must be null unless
the ignition event itself is directly visible; scale must be null unless supported by an explicit measured reference.
If a field cannot be determined from the video use null and list it in unknowns. Do not guess.
fire_sources and nearby_objects must always be arrays; use [] rather than null when empty.
If there is no visible fire, return "fire_sources":[], including when only smoke is visible."""


class UpstreamError(Exception):
    """Network / 5xx / timeout -> run.state failed, retryable."""


class InvalidOutput(Exception):
    """Model answered but output unusable -> needs_review."""

    def __init__(self, msg, raw_text=""):
        super().__init__(msg)
        self.raw_text = raw_text


def _b64(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()


def build_messages(frames):
    content = []
    for k, fr in enumerate(frames, 1):
        content.append({"type": "text", "text": f"Frame {k} at t={fr['t_s']:.1f}s"})
        content.append({"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + _b64(fr["path"])}})
    content.append({"type": "text", "text": PROMPT})
    return [{"role": "user", "content": content}]


def _json_candidates(text):
    """Yield every balanced top-level {...} substring, in order."""
    depth, start, in_str, esc = 0, None, False, False
    for i, ch in enumerate(text):
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}" and depth:
            depth -= 1
            if depth == 0 and start is not None:
                yield text[start:i + 1]


def extract_json(text):
    """Final answer JSON after any thinking; prefer the last object containing fire_sources."""
    visible = re.sub(r"<think>.*?</think>", "", text, flags=re.S)
    if "</think>" in visible:
        visible = visible.split("</think>")[-1]
    for src in (visible, text):
        found = None
        for cand in _json_candidates(src):
            try:
                obj = json.loads(cand)
            except ValueError:
                continue
            if isinstance(obj, dict) and "fire_sources" in obj:
                found = obj
        if found is not None:
            return found
    raise InvalidOutput("No JSON object with 'fire_sources' found in Cosmos response", text)


def _num_list(v, n=None):
    return isinstance(v, list) and (n is None or len(v) == n) and all(
        isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x) for x in v)


def _optional_text(obj, key, raw_text):
    value = obj.get(key)
    if value is not None and not isinstance(value, str):
        raise InvalidOutput(f"{key} must be a string or null", raw_text)
    return value


def validate(obj, duration_s, raw_text="", allow_empty=False):
    fires = obj.get("fire_sources")
    if not isinstance(fires, list):
        raise InvalidOutput("fire_sources is not a list", raw_text)
    if not fires and not allow_empty:
        raise InvalidOutput("Cosmos reported no fire sources in this clip", raw_text)
    seen, out = set(), []
    for fs in fires:
        if not isinstance(fs, dict):
            raise InvalidOutput("fire source entry is not an object", raw_text)
        fid = fs.get("id")
        if not isinstance(fid, str) or not fid or fid in seen:
            raise InvalidOutput(f"missing or duplicate fire id: {fid!r}", raw_text)
        seen.add(fid)
        native_box = fs.get("bbox_2d")
        bb = fs.get("bbox_normalized")
        bbox_source_scale = "0-1"
        if native_box is not None and bb is not None:
            raise InvalidOutput(f"{fid}: provide only one bounding-box coordinate format", raw_text)
        if native_box is not None:
            if not _num_list(native_box, 4):
                raise InvalidOutput(f"{fid}: bbox_2d must be 4 numbers", raw_text)
            nx0, ny0, nx1, ny1 = native_box
            if not (0 <= nx0 < nx1 <= 1000 and 0 <= ny0 < ny1 <= 1000):
                raise InvalidOutput(f"{fid}: bbox_2d out of range or not ordered in 0-1000 coordinates", raw_text)
            bb = [float(v) / 1000 for v in native_box]
            bbox_source_scale = "0-1000"
        if not _num_list(bb, 4):
            raise InvalidOutput(f"{fid}: bbox_normalized must be 4 numbers", raw_text)
        x0, y0, x1, y1 = bb
        if not (0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1):
            raise InvalidOutput(f"{fid}: bbox {bb} out of range or not ordered [x_min,y_min,x_max,y_max]", raw_text)
        ts = fs.get("timestamps_s")
        if not _num_list(ts) or not ts:
            raise InvalidOutput(f"{fid}: timestamps_s must be a non-empty number list", raw_text)
        if any(t < 0 or t > duration_s + 0.5 for t in ts):
            raise InvalidOutput(f"{fid}: timestamps {ts} outside clip duration {duration_s:.1f}s", raw_text)
        nearby = fs.get("nearby_objects", [])
        if not isinstance(nearby, list) or not all(isinstance(v, str) for v in nearby):
            raise InvalidOutput(f"{fid}: nearby_objects must be a list of strings", raw_text)
        out.append({"id": fid, "timestamps_s": [float(t) for t in ts],
                    "bbox_normalized": [float(x) for x in bb],
                    "bbox_source_scale": bbox_source_scale,
                    "image_center_normalized": [(x0 + x1) / 2, (y0 + y1) / 2],
                    "description": str(fs.get("description") or ""),
                    "location_description": _optional_text(fs, "location_description", raw_text),
                    "burning_object": _optional_text(fs, "burning_object", raw_text),
                    "smoke_description": _optional_text(fs, "smoke_description", raw_text),
                    "nearby_objects": nearby})
    unknowns = obj.get("unknowns")
    unknowns = [str(u) for u in unknowns] if isinstance(unknowns, list) else []
    # This input adapter has no camera calibration or measured depth. Never promote
    # a model's estimated metres to an observed quantity.
    depth = None
    cause = obj.get("cause") if isinstance(obj.get("cause"), str) and obj.get("cause") else None
    scale = obj.get("scale") if isinstance(obj.get("scale"), str) and obj.get("scale") else None
    for name, val in (("cause", cause), ("scale", scale), ("depth", depth)):
        if val is None and name not in unknowns and not (name == "depth" and "depth_m" in unknowns):
            unknowns.append(name)
    return {"fire_sources": out, "unknowns": unknowns, "cause": cause, "scale": scale, "depth_m": depth,
            "scene_description": _optional_text(obj, "scene_description", raw_text)}


def _cache_path(sha, model):
    return config.CACHE_DIR / f"{sha}_{PROMPT_ID}_{model.replace('/', '_')}.json"


@config.weave_op
def call_cosmos(frames):
    token = config.get("GPU_BEARER_TOKEN")
    if not token:
        raise UpstreamError("GPU_BEARER_TOKEN not configured")
    body = {"model": MODEL_ID, "messages": build_messages(frames), "temperature": 0, "max_tokens": 4096}
    try:
        r = requests.post(f"{config.COSMOS_URL}/v1/chat/completions", json=body,
                          headers={"Authorization": f"Bearer {token}"}, timeout=config.COSMOS_TIMEOUT_S)
    except requests.RequestException as e:
        raise UpstreamError(f"Cosmos request failed: {type(e).__name__}: {e}") from e
    if r.status_code >= 500 or r.status_code in (401, 403, 408, 429):
        raise UpstreamError(f"Cosmos HTTP {r.status_code}: {r.text[:200]}")
    if r.status_code != 200:
        raise UpstreamError(f"Cosmos HTTP {r.status_code}: {r.text[:200]}")
    try:
        msg = r.json()["choices"][0]["message"]
        text = (msg.get("content") or "")
        reasoning = msg.get("reasoning_content") or msg.get("reasoning") or ""
    except Exception as e:  # noqa: BLE001
        raise UpstreamError(f"Cosmos returned malformed response: {r.text[:200]}") from e
    return (reasoning + "\n" + text) if (reasoning and "fire_sources" not in text) else text


def analyse(frames, duration_s, sha256=None, allow_empty=False):
    """Returns (analysis, observations). Raises UpstreamError / InvalidOutput."""
    t0 = time.time()
    cached = False
    cp = _cache_path(sha256, MODEL_ID) if (config.use_cache() and sha256) else None
    if cp and cp.exists():
        raw = json.loads(cp.read_text())["raw_text"]
        cached = True
    else:
        raw = call_cosmos(frames)
        if cp:
            config.CACHE_DIR.mkdir(exist_ok=True)
            cp.write_text(json.dumps({"raw_text": raw}))
    analysis = {"raw_text": raw, "cached": cached, "frames": [{"t_s": f["t_s"]} for f in frames],
                "latency_s": round(time.time() - t0, 2)}
    try:
        obs = validate(extract_json(raw), duration_s, raw, allow_empty=allow_empty)
    except InvalidOutput as e:
        e.analysis = analysis
        raise
    from . import scene  # lazy: sim worker module
    for fs in obs["fire_sources"]:
        fs["suggested_zone"] = scene.suggest_zone(fs["bbox_normalized"])
    obs["objects"] = []
    return analysis, obs


def propose_associations(views, frame_paths):
    """Ask Cosmos for possible cross-view matches; preserve its output and validate every proposal."""
    t0 = time.monotonic()
    fields = ("id", "view_id", "source_id", "description", "location_description", "burning_object", "smoke_description", "nearby_objects", "bbox_normalized")
    evidence = [{k: f[k] for k in fields if k in f} for v in views for f in v["observations"]["fire_sources"]]
    prompt = ("Suggest possible same physical fire across different camera views. Evidence: " + json.dumps(evidence) +
              ' Return only a JSON object with association_candidates as an array. Each candidate has members '
              '(an array of exact evidence IDs from different views) and reason (a specific visual feature shared '
              'by those sightings). If uncertain return an empty array. Do not infer a match from matching ID numbers; '
              'never invent IDs or group sightings from the same view.')
    result = {"status": "manual_review", "candidates": [], "raw_text": "", "content": "", "reasoning_content": "",
              "prompt_id": "cosmos_association_v2", "prompt": prompt, "model_id": MODEL_ID, "latency_s": 0, "error": None}
    try:
        token = config.get("GPU_BEARER_TOKEN")
        if not token:
            raise UpstreamError("GPU_BEARER_TOKEN not configured")
        if len(views) != len(frame_paths) or not 1 <= len(frame_paths) <= 3:
            raise ValueError("association requires one image for each of one to three views")
        content = []
        for view, path in zip(views, frame_paths):
            content.extend([{"type": "text", "text": "View " + view["view_id"]},
                            {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + _b64(path)}}])
        content.append({"type": "text", "text": prompt})
        r = requests.post(f"{config.COSMOS_URL}/v1/chat/completions", json={"model": MODEL_ID, "messages": [{"role": "user", "content": content}], "temperature": 0.2, "max_tokens": 2048}, headers={"Authorization": f"Bearer {token}"}, timeout=config.COSMOS_TIMEOUT_S)
        result["raw_text"] = getattr(r, "text", "") or ""
        r.raise_for_status()
        body = r.json()
        msg = body["choices"][0]["message"]
        result["model_id"] = body.get("model") or MODEL_ID
        raw = msg.get("content") or ""
        reasoning = msg.get("reasoning_content") or msg.get("reasoning") or ""
        if not isinstance(raw, str) or not isinstance(reasoning, str):
            raise ValueError("association response content must be text")
        result["content"], result["reasoning_content"] = raw, reasoning
        result["raw_text"] = (reasoning + "\n" + raw) if reasoning else raw
        obj = None
        # Prefer the actual answer; some Cosmos servers put the answer in reasoning_content.
        for text in (raw, reasoning):
            visible = re.sub(r"<think>.*?</think>", "", text, flags=re.S)
            if "</think>" in visible:
                visible = visible.split("</think>")[-1]
            # Some Cosmos deployments emit the candidate array directly, including in a JSON fence.
            cleaned = re.sub(r"^\s*```(?:json)?\s*|\s*```\s*$", "", visible.strip(), flags=re.I)
            try:
                candidate = json.loads(cleaned)
                if isinstance(candidate, list):
                    obj = {"association_candidates": candidate}
                elif isinstance(candidate, dict) and "association_candidates" in candidate:
                    obj = candidate
            except ValueError:
                pass
            if obj is None:
                for cand in _json_candidates(visible):
                    try:
                        candidate = json.loads(cand)
                        if isinstance(candidate, dict) and "association_candidates" in candidate:
                            obj = candidate
                    except ValueError:
                        pass
            if obj is not None:
                break
        candidates = obj["association_candidates"] if obj is not None else None
        if not isinstance(candidates, list):
            raise ValueError("missing association_candidates array")
        valid = {f["id"]: f["view_id"] for f in evidence}
        out = []
        for c in candidates:
            if not isinstance(c, dict) or not isinstance(c.get("members"), list) or not isinstance(c.get("reason"), str) or not c["reason"].strip():
                raise ValueError("invalid association proposal")
            ids = c["members"]
            if len(ids) < 2 or not all(isinstance(i, str) and i in valid for i in ids) or len(set(ids)) != len(ids) or len({valid[i] for i in ids}) != len(ids):
                raise ValueError("invalid association membership")
            out.append({"members": ids, "reason": c["reason"].strip()})
        result["candidates"] = out
        result["status"] = "proposed" if out else "manual_review"
    except (UpstreamError, requests.RequestException, KeyError, IndexError, ValueError, TypeError, OSError) as e:
        result["error"] = f"Cosmos association unavailable: {type(e).__name__}: {e}"
    result["latency_s"] = round(time.monotonic() - t0, 2)
    return result
