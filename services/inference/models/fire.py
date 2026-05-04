from ultralytics import YOLO

from config import config


class FireYOLO:
    FIRE_CLASSES = {"fire", "smoke"}

    def __init__(self):
        self.model = YOLO(config.FIRE_MODEL_PATH)

    def predict(self, frame, h: int, w: int) -> list[dict]:
        results = self.model(frame, conf=config.FIRE_CONF, imgsz=config.YOLO_IMGSZ, verbose=False)
        detections = []

        if results[0].boxes is None:
            return detections

        for box in results[0].boxes:
            cls_id = int(box.cls[0].item())
            class_name = self.model.names[cls_id]
            if class_name in self.FIRE_CLASSES:
                detections.append({
                    "route": "emergency",
                    "anomaly_type": class_name,
                    "danger_level": "critical",
                    "description": "화재 위험 감지",
                    "confidence": round(float(box.conf[0].item()), 4),
                    "source_model": "fire_yolo",
                })

        return detections
