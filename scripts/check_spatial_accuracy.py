#!/usr/bin/env python3
"""Evaluate six live demo views against independent annotations, never as inference input."""
import argparse
import json
import math
import re
import sys
from functools import lru_cache
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/fire_localization.json"
THRESHOLD = 0.5


def box_at(source, timestamp):
    series = source.get("bbox_by_frame")
    if series:
        choices = [item for item in series if isinstance(item, dict) and type(item.get("t_s")) in (int, float) and math.isfinite(item["t_s"])]
        if not choices:
            return None, None, "invalid frame series"
        frame = min(choices, key=lambda item: abs(item["t_s"] - timestamp))
        if abs(frame["t_s"] - timestamp) > 0.51:
            return None, frame["t_s"], "nearest frame is too far from reference timestamp"
        box, t, method = frame.get("bbox_normalized"), frame["t_s"], "nearest frame"
    else:
        box, t, method = source.get("bbox_normalized"), source.get("bbox_at_s"), "static box"
    if (not isinstance(box, list) or len(box) != 4 or any(type(x) not in (int, float) or not math.isfinite(x) for x in box)
            or not (0 <= box[0] < box[2] <= 1 and 0 <= box[1] < box[3] <= 1)):
        return None, t, "invalid normalized box"
    return box, t, method


def iou(a, b):
    overlap = max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(0, min(a[3], b[3]) - max(a[1], b[1]))
    union = (a[2]-a[0])*(a[3]-a[1]) + (b[2]-b[0])*(b[3]-b[1]) - overlap
    return overlap / union if union else 0.0


def score(sources, refs, timestamp):
    predictions = []
    for index, source in enumerate(sources):
        box, time, method = box_at(source, timestamp)
        predictions.append({"id": source.get("id", f"unnamed-{index+1}"), "box": box, "timestamp_s": time, "selection": method})
    matrix = [[iou(p["box"], ref["bbox_xyxy_normalized"]) if p["box"] else 0.0 for ref in refs] for p in predictions]

    # Maximize number of threshold-qualified pairs first, then their total IoU.
    @lru_cache(None)
    def assignment(index, used):
        if index == len(predictions):
            return (0, 0.0, ())
        best = assignment(index + 1, used)
        for j, overlap in enumerate(matrix[index]):
            if not (used & (1 << j)) and overlap >= THRESHOLD:
                count, total, pairs = assignment(index + 1, used | (1 << j))
                candidate = (count + 1, total + overlap, ((index, j),) + pairs)
                if candidate[:2] > best[:2]:
                    best = candidate
        return best

    count, _, pairs = assignment(0, 0)
    matched_p, matched_r = {p for p, _ in pairs}, {r for _, r in pairs}
    precision = count / len(predictions) if predictions else (1.0 if not refs else 0.0)
    recall = count / len(refs) if refs else (1.0 if not predictions else 0.0)
    return {"predicted_count": len(predictions), "reference_count": len(refs), "matched_count": count,
            "precision": precision, "recall": recall, "passed": precision == 1.0 and recall == 1.0,
            "matches": [{"prediction": predictions[p], "reference_id": refs[r]["local_id"], "iou": round(matrix[p][r], 4)} for p, r in pairs],
            "unmatched_predictions": [{**p, "best_iou": round(max(matrix[i], default=0.0), 4)} for i, p in enumerate(predictions) if i not in matched_p],
            "unmatched_references": [{"id": ref["local_id"], "box": ref["bbox_xyxy_normalized"],
                                      "best_iou": round(max((row[i] for row in matrix), default=0.0), 4)}
                                     for i, ref in enumerate(refs) if i not in matched_r]}


def main():
    parser = argparse.ArgumentParser(description="Score two live 3-view runs against independent frame annotations (IoU >= 0.5).")
    parser.add_argument("--run-ids", nargs=2, required=True, metavar=("RUN1", "RUN2"))
    parser.add_argument("--out", type=Path, required=True, help="Write full JSON report to this path")
    args = parser.parse_args()
    report = {"all_passed": False, "threshold_iou": THRESHOLD, "timestamp_s": 2.5,
              "identity_accuracy": "not established: no independent cross-view physical identity ground truth", "views": [], "errors": []}
    try:
        fixture = json.loads(FIXTURE.read_text())
        by_hash = {v["source_sha256"]: (name, v) for name, v in fixture["views"].items()}
        if len(by_hash) != 6:
            raise ValueError("Reference fixture must contain six unique hashes")
        seen = set()
        for rid in args.run_ids:
            if not re.fullmatch(r"r_[A-Za-z0-9_]+", rid):
                raise ValueError("Invalid run ID")
            try:
                response = requests.get(f"http://127.0.0.1:8090/api/runs/{rid}", timeout=20)
                response.raise_for_status()
                run = response.json()
            except (requests.RequestException, ValueError) as exc:
                raise ValueError(f"Could not fetch run {rid}: {type(exc).__name__}") from exc
            refs = run.get("video_refs") or []
            views = {v.get("view_id"): v for v in (run.get("analysis") or {}).get("views", [])}
            if len(refs) != 3 or len(views) != 3:
                report["errors"].append(f"{rid}: expected three source views")
            for ref in refs:
                digest = ref.get("sha256")
                if digest not in by_hash or digest in seen:
                    report["errors"].append(f"{rid}/{ref.get('view_id')}: unknown or repeated source hash")
                    continue
                seen.add(digest)
                name, reference = by_hash[digest]
                view = views.get(ref.get("view_id")) or {}
                observations = view.get("observations") or {}
                spatial = (view.get("analysis") or {}).get("spatial_review") or {}
                baseline = spatial.get("original_observations")
                sources = observations.get("fire_sources")
                item = {"run_id": rid, "view_id": ref.get("view_id"), "reference": name, "source_sha256": digest}
                if not isinstance(sources, list):
                    report["errors"].append(f"{rid}/{ref.get('view_id')}: effective observations unavailable")
                else:
                    item["effective"] = score(sources, reference["boxes"], 2.5)
                if isinstance(baseline, dict) and isinstance(baseline.get("fire_sources"), list):
                    item["cosmos_baseline"] = score(baseline["fire_sources"], reference["boxes"], 2.5)
                else:
                    report["errors"].append(f"{rid}/{ref.get('view_id')}: preserved Cosmos baseline unavailable")
                report["views"].append(item)
            association = (run.get("analysis") or {}).get("association") or {}
            if (association.get("room_status") not in ("unverified", "contradicted")
                    or association.get("status") != "manual_review" or association.get("candidates") != []
                    or (run.get("analysis") or {}).get("association_candidates") != []):
                report["errors"].append(f"{rid}: room must remain unverified or contradicted, with manual review and no asserted candidates")
        if seen != set(by_hash):
            report["errors"].append("The two runs do not cover exactly the six distinct reference videos")
        report["summary"] = {}
        for key in ("effective", "cosmos_baseline"):
            scores = [v[key] for v in report["views"] if key in v]
            matched = sum(v["matched_count"] for v in scores)
            predictions = sum(v["predicted_count"] for v in scores)
            references = sum(v["reference_count"] for v in scores)
            report["summary"][key] = {"evaluated_views": len(scores), "matched": matched, "predictions": predictions, "references": references,
                                      "precision": matched / predictions if predictions else None,
                                      "recall": matched / references if references else None}
        report["all_passed"] = not report["errors"] and len(report["views"]) == 6 and all(v.get("effective", {}).get("passed") for v in report["views"])
    except (OSError, ValueError, KeyError, TypeError) as exc:
        report["errors"].append(f"{type(exc).__name__}: {exc}")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n")
    print(f"Spatial evaluation: {'PASS' if report['all_passed'] else 'FAIL'}; {len(report['views'])} views; report: {args.out}")
    return 0 if report["all_passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
