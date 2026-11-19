"""
Evidence photos.

Every detected class is saved as an annotated photo:

    evidence/<Location>/<Class>/<YYYYMMDD_HHMMSS>_<source>_<confidence>.jpg

and logged in evidence/evidence_log.csv (time, location, class, count,
highest confidence, source, file).
"""
import csv
import re
import threading
from datetime import datetime
from pathlib import Path

import cv2

import config
from core.classification import display_name
from core.detector import draw_detections

_lock = threading.Lock()
LOG_HEADER = ["time", "location", "class", "count", "highest_confidence", "source", "file"]


def _safe(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "_", name).strip("_") or "Unknown"


def save_evidence(image_bgr, detections: list[dict], location_name: str, source: str,
                  classes: set[str] | None = None) -> list[Path]:
    """Save one annotated photo per detected class. Returns the saved file paths."""
    if image_bgr is None or not detections:
        return []

    annotated = draw_detections(image_bgr.copy(), detections)
    now = datetime.now()
    stamp = now.strftime("%Y%m%d_%H%M%S")
    saved = []

    by_class = {}
    for det in detections:
        by_class.setdefault(det["class_name"], []).append(det)

    with _lock:
        log_path = Path(config.EVIDENCE_DIR) / "evidence_log.csv"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        new_log = not log_path.exists()
        with open(log_path, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            if new_log:
                writer.writerow(LOG_HEADER)
            for class_name, dets in by_class.items():
                if classes is not None and class_name not in classes:
                    continue
                best = max(d["confidence"] for d in dets)
                folder = (Path(config.EVIDENCE_DIR) / _safe(location_name)
                          / _safe(display_name(class_name)))
                folder.mkdir(parents=True, exist_ok=True)
                path = folder / f"{stamp}_{_safe(source)}_{int(best * 100)}.jpg"
                counter = 1
                while path.exists():  # two photos in the same second
                    path = folder / f"{stamp}_{_safe(source)}_{int(best * 100)}_{counter}.jpg"
                    counter += 1
                cv2.imwrite(str(path), annotated)
                writer.writerow([now.strftime("%Y-%m-%d %H:%M:%S"), location_name,
                                 display_name(class_name), len(dets), f"{best:.3f}",
                                 source, str(path)])
                saved.append(path)
    return saved
