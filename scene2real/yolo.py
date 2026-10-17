"""Optional YOLO11 supplement (CoreWeave). Never blocks the pipeline."""
import base64

import requests

from . import config


def _walk_detections(data):
    """Best-effort extraction of [{label, conf, t_s, bbox_normalized}] from unknown response shapes."""
    out = []

    def visit(node, t=None, w=None, h=None):
        if isinstance(node, dict):
            w = node.get("width", node.get("frame_width", w))
            h = node.get("height", node.get("frame_height", h))
            t = node.get("t_s", node.get("timestamp_s", node.get("time_s", t)))
            label = node.get("label", node.get("class_name", node.get("name")))
            bb = node.get("bbox", node.get("xyxy", node.get("box")))
            conf = node.get("conf", node.get("confidence", node.get("score")))
            if label is not None and isinstance(bb, list) and len(bb) == 4:
                if all(0 <= v <= 1 for v in bb):
                    nb = [float(v) for v in bb]
                elif w and h:
                    nb = [bb[0] / w, bb[1] / h, bb[2] / w, bb[3] / h]
                else:
                    nb = None
                if nb:
                    out.append({"label": str(label), "conf": round(float(conf or 0), 3), "t_s": t,
                                "bbox_normalized": [round(min(max(v, 0), 1), 4) for v in nb], "source": "yolo11"})
            for v in node.values():
                visit(v, t, w, h)
        elif isinstance(node, list):
            for v in node:
                visit(v, t, w, h)

    visit(data)
    return out


def detect(clip_path):
    """Returns (objects, note). Never raises."""
    token = config.get("GPU_BEARER_TOKEN")
    if not token:
        return [], "yolo skipped: no GPU token"
    try:
        with open(clip_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        r = requests.post(f"{config.YOLO_URL}/v1/infer-base64",
                          json={"video_base64": b64, "filename": "clip.mp4", "include_frames": True},
                          headers={"Authorization": f"Bearer {token}"}, timeout=90)
        if r.status_code != 200:
            return [], f"yolo skipped: HTTP {r.status_code}"
        objs = _walk_detections(r.json())
        return objs[:200], "ok"
    except Exception as e:  # noqa: BLE001
        return [], f"yolo skipped: {type(e).__name__}: {str(e)[:100]}"
