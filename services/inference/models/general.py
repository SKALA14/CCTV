from ultralytics import YOLO

from config import config
from models.optical_flow import OpticalFlowGate


class GeneralYOLO:
    def __init__(self):
        self.model = YOLO(config.GENERAL_MODEL_PATH)
        self.target_classes = {"person"}
        self.flow_gate = OpticalFlowGate(
            resize_width=config.GENERAL_OPTICAL_FLOW_RESIZE_WIDTH,
            threshold=config.GENERAL_OPTICAL_FLOW_THRESHOLD,
            percentile=config.GENERAL_OPTICAL_FLOW_PERCENTILE,
            state_ttl_sec=config.GENERAL_OPTICAL_FLOW_STATE_TTL_SEC,
        )

    def predict(self, frame, h: int, w: int, camera_id: str) -> list[dict]:
        '''
        general route 후보를 반환한다.

        입력
        - frame, h, w: 현재 프레임과 크기 정보.
        - camera_id: optical flow의 직전 프레임 상태를 분리하는 기준.

        출력
        - route=general detection 목록.
        - optical flow spike가 없거나 사람 객체가 없으면 빈 목록을 반환한다.
        '''
        flow_result = self.flow_gate.evaluate(camera_id, frame)
        if config.GENERAL_OPTICAL_FLOW_ENABLED and not flow_result.is_spike:
            return []

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
                    "flow_score": flow_result.score,
                    "flow_threshold": config.GENERAL_OPTICAL_FLOW_THRESHOLD,
                    "source_model": "general_yolo",
                })

        return detections
