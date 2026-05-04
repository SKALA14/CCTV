import math

from ultralytics import YOLO

from config import config
from models.common import clamp_bbox


class PoseYOLO:
    # COCO keypoint 인덱스
    _NOSE = 0
    _L_SHOULDER, _R_SHOULDER = 5, 6
    _L_HIP, _R_HIP = 11, 12

    def __init__(self):
        self.model = YOLO(config.POSE_MODEL_PATH)

    @staticmethod
    def _is_fallen(pts, cf, bbox) -> bool:
        """
        점수 기준 (2점 이상 → 낙상):
          +2  토르소 각도: 어깨-엉덩이 벡터가 수직에서 55도 이상 기울어진 경우
          +2  코 위치: nose y > 엉덩이 중점 y (머리가 엉덩이보다 아래)
          +1  bbox 비율: width / height > 1.3
        """
        L_SH, R_SH = PoseYOLO._L_SHOULDER, PoseYOLO._R_SHOULDER
        L_HIP, R_HIP = PoseYOLO._L_HIP, PoseYOLO._R_HIP
        NOSE = PoseYOLO._NOSE
        T = config.POSE_KEYPOINT_CONF

        if not (cf[L_SH] > T and cf[R_SH] > T and cf[L_HIP] > T and cf[R_HIP] > T):
            return False

        sh_mid = (pts[L_SH] + pts[R_SH]) / 2
        hip_mid = (pts[L_HIP] + pts[R_HIP]) / 2

        dx = float(hip_mid[0] - sh_mid[0])
        dy = float(hip_mid[1] - sh_mid[1])
        torso_len = math.hypot(dx, dy)
        if torso_len < 1e-6:
            return False

        angle = math.degrees(math.acos(min(abs(dy) / torso_len, 1.0)))

        score = 0
        if angle > config.FALL_TORSO_ANGLE_THRESH:
            score += 2
        if cf[NOSE] > T and float(pts[NOSE][1]) > float(hip_mid[1]):
            score += 2

        x1, y1, x2, y2 = bbox
        bw, bh = float(x2 - x1), float(y2 - y1)
        if bh > 0 and bw / bh > config.FALL_BBOX_RATIO_THRESH:
            score += 1

        return score >= 2

    def predict(self, frame, h: int, w: int) -> list[dict]:
        results = self.model(frame, conf=config.POSE_CONF, imgsz=config.YOLO_IMGSZ, verbose=False)
        detections = []

        if results[0].boxes is None or results[0].keypoints is None:
            return detections

        kpts = results[0].keypoints.xy
        confs = results[0].keypoints.conf
        boxes = results[0].boxes

        for idx, box in enumerate(boxes):
            cls_id = int(box.cls[0].item())
            if self.model.names[cls_id] != "person":
                continue

            fallen = self._is_fallen(kpts[idx], confs[idx], box.xyxy[0])
            if not fallen:
                continue

            detections.append({
                "route": "emergency",
                "anomaly_type": "fallen",
                "danger_level": "critical",
                "description": "작업자 낙상 감지",
                "confidence": round(float(box.conf[0].item()), 4),
                "bbox": clamp_bbox(box.xyxy[0].tolist(), h, w),
                "keypoints": results[0].keypoints.data[idx].tolist(),
                "source_model": "pose_yolo",
            })

        return detections
