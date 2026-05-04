from ultralytics import YOLO

from config import config


class GeneralYOLO:
    def __init__(self):
        self.model = YOLO(config.GENERAL_MODEL_PATH)
        self.target_classes = {"person"}

    def predict(self, frame, h: int, w: int) -> list[dict]:
        results = self.model(frame, conf=config.GENERAL_CONF, imgsz=config.YOLO_IMGSZ, verbose=False)
        detections = []

        if results[0].boxes is None:
            return detections

        for box in results[0].boxes:
            cls_id = int(box.cls[0].item())
            class_name = self.model.names[cls_id]
            if class_name in self.target_classes:
                detections.append({
                    "route": "general",
                    "anomaly_type": "candidate",
                    "confidence": round(float(box.conf[0].item()), 4),
                    "source_model": "general_yolo",
                })

        return detections
