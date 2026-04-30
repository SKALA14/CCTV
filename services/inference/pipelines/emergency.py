# "emergency" Consumer Group으로 프레임을 읽어 YOLO 추론 후 즉시 알람을 발행하는 프로세스.
# 정의: run() — XREADGROUP 루프, EmergencyYOLO.predict 호출, 탐지 시 XADD(alerts).
# 입력: Redis Stream "frames" 메시지 — {frame_path, camera_id, timestamp}.
# 출력: 긴급 상황 시 "alerts" 스트림에 XADD; 항상 XACK 후 mark_processed 호출.

import logging
import time
from collections import deque
from datetime import datetime
from pathlib import Path

import cv2

from config import config
from models.yolo import EmergencyYOLO
from redis_client import xreadgroup, xadd, xack, mark_processed

logger = logging.getLogger(__name__)

GROUP      = "emergency"
CONSUMER   = "emergency-worker"
MIN_FRAMES = 3   
WINDOW_SEC = 5.0
_COLORS    = {
    "fallen": (0, 0, 255),
    "fire":   (0, 128, 255),
    "smoke":  (128, 128, 128),
    "person": (0, 255, 0),
}


def _annotate_and_save(frame_path: str, detections: list[dict]) -> None:
    frame = cv2.imread(frame_path)
    if frame is None:
        return

    for det in detections:
        bbox     = det.get("bbox")
        track_id = det.get("track_id")
        atype    = det.get("anomaly_type", "person")

        if not bbox:
            continue

        x1, y1, x2, y2 = map(int, bbox)
        color = _COLORS.get(atype, (255, 255, 255))
        label = f"id:{track_id} {atype}" if track_id is not None else atype

        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
        cv2.putText(frame, label, (x1, y1 - 6),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2)

    cv2.imwrite(frame_path, frame)


def run():
    model = EmergencyYOLO()
    fallen_timestamps: dict[str, deque] = {}  # {camera_id: deque of timestamps}
    logger.info("emergency pipeline started")

    while True:
        messages = xreadgroup(config.FRAMES_STREAM, GROUP, CONSUMER)
        for msg_id, fields in messages:
            print("Received message")
            frame_path = fields.get("frame_path", "")
            camera_id  = fields.get("camera_id", config.CAMERA_ID)

            if not frame_path: # 경로가 존재하지 않는 경우 
                xack(config.FRAMES_STREAM, GROUP, msg_id)
                continue

            detections = model.predict(frame_path)

            for det in detections:
                anomaly_type = det.get("anomaly_type", "")

                if anomaly_type in ("fire", "smoke"):
                    xadd(config.ALERTS_STREAM, {
                        "camera_id": camera_id,
                        "frame": Path(frame_path).name,
                        "timestamp": str(datetime.now()),
                        "anomaly_type": anomaly_type,
                        "danger_level": "critical",
                        "description": "화재 위험 감지",
                    })
                    continue

                elif anomaly_type == "fallen":
                    if camera_id not in fallen_timestamps:
                        fallen_timestamps[camera_id] = deque()

                    now = time.time()
                    fallen_timestamps[camera_id].append(now)

                    # 윈도우 밖 제거
                    cutoff = now - WINDOW_SEC
                    while fallen_timestamps[camera_id] and fallen_timestamps[camera_id][0] < cutoff:
                        fallen_timestamps[camera_id].popleft()

                    if len(fallen_timestamps[camera_id]) >= MIN_FRAMES:
                        xadd(config.ALERTS_STREAM, {
                            "camera_id":    camera_id,
                            "frame":        Path(frame_path).name,
                            "timestamp":    str(datetime.now()),
                            "anomaly_type": "fallen",
                            "danger_level": "critical",
                            "description":  "작업자 낙상 감지",
                        })
                        fallen_timestamps[camera_id].clear()  # 알람 후 리셋

            if config.ANNOTATE_FRAMES and detections:
                _annotate_and_save(frame_path, detections)

            xack(config.FRAMES_STREAM, GROUP, msg_id)
            mark_processed(frame_path)
