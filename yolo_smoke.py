"""Check local YOLO detection on a sample image. Run: uv run yolo_smoke.py"""
from ultralytics import YOLO

model = YOLO("yolo11n.pt")
result = model("https://ultralytics.com/images/bus.jpg", verbose=False)[0]
names = [result.names[int(c)] for c in result.boxes.cls]
print(f"YOLO OK: {len(names)} detections -> {sorted(set(names))}")
