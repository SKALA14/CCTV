# services/inference/models/pose.py
"""낙상 판정 Pose YOLO 추론.

점수제 판정 (score >= 2 → fallen):
  - torso 기울기 > FALL_TORSO_ANGLE_THRESH: +2  (옆 낙상)
  - 코 y좌표 > 엉덩이 y좌표: +2                 (옆 낙상 보강)
  - bbox 가로/세로 비 > FALL_BBOX_RATIO_THRESH: +1
  - bbox 높이 급감 (최근 최대 대비): +2           (정면 낙상)
"""

from __future__ import annotations

import logging
import math
import time
from collections import deque

from ultralytics import YOLO

from config import config
from models.common import clamp_bbox

logger = logging.getLogger(__name__)


class PoseYOLO:
    # COCO keypoint 인덱스
    _NOSE = 0
    _L_SHOULDER, _R_SHOULDER = 5, 6
    _L_HIP, _R_HIP = 11, 12

    def __init__(self) -> None:
        self.model = YOLO(config.POSE_MODEL_PATH)
        # 카메라별 bbox 높이 이력: {camera_id: deque of (mono_time, max_person_height)}
        self._height_history: dict[str, deque] = {}

    def _check_height_drop(self, camera_id: str, current_height: float) -> bool:
        """최근 프레임들의 최대 bbox 높이 대비 급격한 감소를 감지.

        서 있던 사람의 bbox 높이가 갑자기 줄어들면 정면 낙상.
        높이가 50px 미만인 작은 인물은 무시 (원거리 오탐 방지).
        """
        buf = self._height_history.setdefault(camera_id, deque(maxlen=30))
        now = time.monotonic()

        # 윈도우 밖 이력 정리
        cutoff = now - config.FALL_HEIGHT_HISTORY_SEC
        while buf and buf[0][0] < cutoff:
            buf.popleft()

        dropped = False
        if buf:
            max_prev = max(h for _, h in buf)
            if max_prev > 50 and current_height / max_prev < config.FALL_HEIGHT_DROP_RATIO:
                logger.info("[pose] 높이 급감: %.0f → %.0f (ratio=%.2f, max_prev=%.0f)",
                            max_prev, current_height, current_height / max_prev, max_prev)
                dropped = True

        buf.append((now, current_height))
        return dropped

    @staticmethod
    def _is_fallen(pts, cf, bbox) -> tuple[bool, dict]:
        """점수제 낙상 판정. 2점 이상이면 낙상. (score_detail 함께 반환)"""
        L_SH, R_SH = PoseYOLO._L_SHOULDER, PoseYOLO._R_SHOULDER
        L_HIP, R_HIP = PoseYOLO._L_HIP, PoseYOLO._R_HIP
        NOSE = PoseYOLO._NOSE
        T = config.POSE_KEYPOINT_CONF

        detail = {"angle": 0.0, "ratio": 0.0, "score": 0, "kp_ok": False}

        if not (cf[L_SH] > T and cf[R_SH] > T and cf[L_HIP] > T and cf[R_HIP] > T):
            logger.debug("[pose] 키포인트 신뢰도 부족: L_SH=%.2f R_SH=%.2f L_HIP=%.2f R_HIP=%.2f (thresh=%.2f)",
                         float(cf[L_SH]), float(cf[R_SH]), float(cf[L_HIP]), float(cf[R_HIP]), T)
            return False, detail

        detail["kp_ok"] = True
        sh_mid = (pts[L_SH] + pts[R_SH]) / 2
        hip_mid = (pts[L_HIP] + pts[R_HIP]) / 2

        dx = float(hip_mid[0] - sh_mid[0])
        dy = float(hip_mid[1] - sh_mid[1])
        torso_len = math.hypot(dx, dy)
        if torso_len < 1e-6:
            return False, detail

        angle = math.degrees(math.acos(min(abs(dy) / torso_len, 1.0)))
        detail["angle"] = angle

        score = 0
        if angle > config.FALL_TORSO_ANGLE_THRESH:
            score += 2
        if cf[NOSE] > T and float(pts[NOSE][1]) > float(hip_mid[1]):
            score += 2

        x1, y1, x2, y2 = bbox
        bw, bh = float(x2 - x1), float(y2 - y1)
        ratio = bw / bh if bh > 0 else 0.0
        detail["ratio"] = ratio
        if bh > 0 and ratio > config.FALL_BBOX_RATIO_THRESH:
            score += 1

        detail["score"] = score
        return score >= 2, detail

    def predict(self, frame, h: int, w: int, camera_id: str = "") -> list[dict]:
        """프레임에서 사람을 찾고 낙상이면 detection 추가."""
        results = self.model(frame, conf=config.POSE_CONF, imgsz=config.POSE_IMGSZ, verbose=False)
        detections: list[dict] = []

        if results[0].boxes is None or results[0].keypoints is None:
            logger.debug("[pose] 사람 감지 없음 (boxes=%s keypoints=%s)",
                         results[0].boxes is not None, results[0].keypoints is not None)
            return detections

        kpts = results[0].keypoints.xy
        confs = results[0].keypoints.conf
        boxes = results[0].boxes

        person_count = 0
        max_height = 0.0

        for idx, box in enumerate(boxes):
            cls_id = int(box.cls[0].item())
            if self.model.names[cls_id] != "person":
                continue
            person_count += 1
            person_conf = float(box.conf[0].item())
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            bbox_height = y2 - y1
            max_height = max(max_height, bbox_height)

            fallen, detail = self._is_fallen(kpts[idx], confs[idx], box.xyxy[0])

            # 정면 낙상: 키포인트 기반으로 안 잡혀도 높이 급감이면 낙상 판정
            height_dropped = False
            if camera_id and not fallen and detail["kp_ok"]:
                height_dropped = self._check_height_drop(camera_id, bbox_height)
                if height_dropped:
                    detail["score"] += 2
                    fallen = detail["score"] >= 2

            if not fallen:
                logger.debug("[pose] person#%d conf=%.2f angle=%.1f ratio=%.2f score=%d → standing",
                             idx, person_conf, detail["angle"], detail["ratio"], detail["score"])
                continue

            reason = "작업자 낙상 감지"
            detections.append({
                "route": "emergency",
                "anomaly_type": "fallen",
                "danger_level": "critical",
                "description": reason,
                "confidence": round(person_conf, 4),
                "bbox": clamp_bbox(box.xyxy[0].tolist(), h, w),
                "source_model": "pose_yolo",
            })

        # 높이 이력 업데이트 (fallen 판정 여부와 무관하게 서 있는 높이 기록)
        if camera_id and max_height > 0:
            buf = self._height_history.setdefault(camera_id, deque(maxlen=30))
            now = time.monotonic()
            cutoff = now - config.FALL_HEIGHT_HISTORY_SEC
            while buf and buf[0][0] < cutoff:
                buf.popleft()
            buf.append((now, max_height))

        if person_count == 0:
            logger.info("[pose] 사람 감지 0명 (imgsz=%d, conf_thresh=%.2f)",
                        config.POSE_IMGSZ, config.POSE_CONF)

        return detections
