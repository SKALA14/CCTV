# services/inference/models/fire.py
"""Fire/Smoke YOLO 추론."""

from __future__ import annotations

from ultralytics import YOLO

from config import config


class FireYOLO:
    # 소문자 정규화 후 비교 — 모델마다 대소문자 다름 (fire_smoke.pt: 'Fire'/'Smoke', fire.pt: 'fire'/'smoke')
    FIRE_CLASSES = {"fire", "smoke"}

    def __init__(self) -> None:
        self.model = YOLO(config.FIRE_MODEL_PATH)

    def predict(self, frame, h: int, w: int) -> list[dict]:
        """프레임에서 fire/smoke를 감지해 detection 리스트 반환."""
        results = self.model(frame, conf=config.FIRE_CONF, imgsz=config.YOLO_IMGSZ, verbose=False)
        detections: list[dict] = []

        if results[0].boxes is None:
            return detections

        for box in results[0].boxes:
            cls_id = int(box.cls[0].item())
            class_name = self.model.names[cls_id]
            normalized = class_name.lower()   # 'Fire' → 'fire', 'Smoke' → 'smoke'
            if normalized in self.FIRE_CLASSES:
                detections.append({
                    "route": "emergency",
                    "anomaly_type": normalized,  # 항상 소문자로 저장
                    "danger_level": "critical",
                    "description": "화재 위험 감지",
                    "confidence": round(float(box.conf[0].item()), 4),
                    "source_model": "fire_yolo",
                    "bbox": box.xyxy[0].tolist(),  # [x1, y1, x2, y2]
                })

        return detections
