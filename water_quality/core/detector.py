"""
YOLO inference and drawing. Uses your existing trained weights; nothing is trained here.
"""
from pathlib import Path

import cv2
import numpy as np

import config


class WaterDetector:
    def __init__(self, model_path=config.MODEL_PATH):
        model_path = Path(model_path)
        if not model_path.exists():
            raise FileNotFoundError(f"Model weights not found at: {model_path}")
        from ultralytics import YOLO  # imported here so the rest of the app loads fast
        self.model = YOLO(str(model_path))

    def detect(self, frame_bgr: np.ndarray, confidence: float = config.DEFAULT_CONFIDENCE,
               annotate: bool = True):
        """Run detection on a BGR image. Returns (annotated_bgr or None, detections)."""
        result = self.model.predict(frame_bgr, conf=confidence, imgsz=config.IMG_SIZE,
                                    verbose=False)[0]
        detections = []

        if result.probs is not None:
            # Classification model: one label for the whole frame
            class_id = int(result.probs.top1)
            score = float(result.probs.top1conf)
            if score >= confidence:
                h, w = frame_bgr.shape[:2]
                detections.append({
                    "class_id": class_id,
                    "class_name": config.CLASS_NAMES.get(class_id, str(class_id)),
                    "confidence": score,
                    "box": (0, 0, w - 1, h - 1),
                })
        else:
            for box in result.boxes:
                class_id = int(box.cls[0])
                x1, y1, x2, y2 = (int(v) for v in box.xyxy[0].tolist())
                detections.append({
                    "class_id": class_id,
                    "class_name": config.CLASS_NAMES.get(class_id, str(class_id)),
                    "confidence": float(box.conf[0]),
                    "box": (x1, y1, x2, y2),
                })

        annotated = draw_detections(frame_bgr.copy(), detections) if annotate else None
        return annotated, detections


def draw_detections(image: np.ndarray, detections: list[dict]) -> np.ndarray:
    h, w = image.shape[:2]
    scale = max(0.5, min(w, h) / 900)
    thickness = max(2, int(round(scale * 2)))

    for det in detections:
        x1, y1, x2, y2 = det["box"]
        color = config.CLASS_COLORS_BGR.get(det["class_name"], (80, 80, 80))
        label = f"{config.DISPLAY_NAMES.get(det['class_name'], det['class_name'])} {det['confidence']:.2f}"

        cv2.rectangle(image, (x1, y1), (x2, y2), color, thickness)
        (tw, th), baseline = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, scale, 1)
        top = max(y1 - th - baseline - 6, 0)
        cv2.rectangle(image, (x1, top), (x1 + tw + 10, top + th + baseline + 6), color, -1)
        cv2.putText(image, label, (x1 + 5, top + th + 3), cv2.FONT_HERSHEY_SIMPLEX,
                    scale, (255, 255, 255), 1, cv2.LINE_AA)
    return image


def decode_image(data: bytes) -> np.ndarray | None:
    """Turn uploaded file bytes into a BGR image (or None if unreadable)."""
    array = np.frombuffer(data, dtype=np.uint8)
    return cv2.imdecode(array, cv2.IMREAD_COLOR)


def to_rgb(image_bgr: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
