"""Cosmos-Reason (CoreWeave) fire observation: frames -> strict JSON -> validated observations."""
import base64
import json
import re
import time

import requests

from . import config

PROMPT_ID = "cosmos_fire_obs_v1"
MODEL_ID = config.COSMOS_MODEL

PROMPT = """You are analysing frames sampled in time order from a short video of a warehouse. Look for fire or smoke sources.
Respond with ONLY one JSON object (no markdown fences, no commentary after it) with exactly this schema:
{"fire_sources":[{"id":"F1","timestamps_s":[<frame times where visible>],"bbox_normalized":[x_min,y_min,x_max,y_max],"description":"<what is burning and where>"}],
 "cause":<string or null>,"scale":<string or null>,"depth_m":<number or null>,"unknowns":[<names of fields you could not determine>]}
Rules: ids are F1, F2, ... unique. bbox_normalized values are 0-1 fractions of the image, origin top-left, x_min<x_max, y_min<y_max.
timestamps_s must come from the frame times given. If a field cannot be determined from the video use null and list it in unknowns. Do not guess.
If there is no fire, return "fire_sources":[]."""


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
        isinstance(x, (int, float)) and not isinstance(x, bool) for x in v)


def validate(obj, duration_s, raw_text=""):
    fires = obj.get("fire_sources")
    if not isinstance(fires, list):
        raise InvalidOutput("fire_sources is not a list", raw_text)
    if not fires:
        raise InvalidOutput("Cosmos reported no fire sources in this clip", raw_text)
    seen, out = set(), []
    for fs in fires:
        if not isinstance(fs, dict):
            raise InvalidOutput("fire source entry is not an object", raw_text)
        fid = fs.get("id")
        if not isinstance(fid, str) or not fid or fid in seen:
            raise InvalidOutput(f"missing or duplicate fire id: {fid!r}", raw_text)
        seen.add(fid)
        bb = fs.get("bbox_normalized")
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
        out.append({"id": fid, "timestamps_s": [float(t) for t in ts],
                    "bbox_normalized": [float(x) for x in bb],
                    "description": str(fs.get("description") or "")})
    unknowns = obj.get("unknowns")
    unknowns = [str(u) for u in unknowns] if isinstance(unknowns, list) else []
    depth = obj.get("depth_m")
    depth = float(depth) if isinstance(depth, (int, float)) and not isinstance(depth, bool) else None
    cause = obj.get("cause") if isinstance(obj.get("cause"), str) and obj.get("cause") else None
    scale = obj.get("scale") if isinstance(obj.get("scale"), str) and obj.get("scale") else None
    for name, val in (("cause", cause), ("scale", scale), ("depth", depth)):
        if val is None and name not in unknowns and not (name == "depth" and "depth_m" in unknowns):
            unknowns.append(name)
    return {"fire_sources": out, "unknowns": unknowns, "cause": cause, "scale": scale, "depth_m": depth}


def _cache_path(sha, model):
    return config.CACHE_DIR / f"{sha}_{PROMPT_ID}_{model.replace('/', '_')}.json"


@config.weave_op
def call_cosmos(frames):
    token = config.get("GPU_BEARER_TOKEN")
    if not token:
        raise UpstreamError("GPU_BEARER_TOKEN not configured")
    body = {"model": MODEL_ID, "messages": build_messages(frames), "temperature": 0.2, "max_tokens": 4096}
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


def analyse(frames, duration_s, sha256=None):
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
        obs = validate(extract_json(raw), duration_s, raw)
    except InvalidOutput as e:
        e.analysis = analysis
        raise
    from . import scene  # lazy: sim worker module
    for fs in obs["fire_sources"]:
        fs["suggested_zone"] = scene.suggest_zone(fs["bbox_normalized"])
    obs["objects"] = []
    return analysis, obs
