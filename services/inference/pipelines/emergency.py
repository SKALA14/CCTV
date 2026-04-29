# "emergency" Consumer Group으로 프레임을 읽어 YOLO 추론 후 즉시 알람을 발행하는 프로세스.
# 정의: run() — XREADGROUP 루프, EmergencyYOLO.predict 호출, 탐지 시 XADD(alerts).
# 입력: Redis Stream "frames" 메시지 — {frame_path, camera_id, timestamp}.
# 출력: 긴급 상황 시 "alerts" 스트림에 XADD; 항상 XACK 후 mark_processed 호출.

import json
import logging
from datetime import datetime
from pathlib import Path

from config import config
from models.yolo import EmergencyYOLO
from redis_client import xreadgroup, xadd, xack, mark_processed

logger = logging.getLogger(__name__)

GROUP = "emergency"
CONSUMER = "emergency-worker"

def build_output_payload(frame_path: str, anomaly_type: str, detections: list[dict]) -> dict:
    """
    출력 형식을 VLM / downstream 모듈에 넘기기 좋은 JSON 구조로 변환
    """
    timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    formatted_detections = []

    for idx, det in enumerate(detections, start=1):
        formatted_detections.append({
            "track_id": det.get("track_id", idx),
            "class": det["class"],
            "conf": det["confidence"],
            "bbox": det["bbox"],
            "keypoints": det.get("keypoints")
        })

    return {
        "frame": Path(frame_path).name,
        "timestamp": timestamp,
        "anomaly_type": anomaly_type,
        "detections": formatted_detections
    }


def run():
    model = EmergencyYOLO()
    logger.info("emergency pipeline started")

    while True:
        messages = xreadgroup(config.FRAMES_STREAM, GROUP, CONSUMER)

        for msg_id, fields in messages:
            frame_path = fields.get("frame_path", "")
            camera_id = fields.get("camera_id", config.CAMERA_ID)

            detections = model.predict(frame_path)

            if detections:
                payload = build_output_payload(frame_path, "emergency", detections)
                xadd(config.ALERTS_STREAM, {
                    "camera_id": camera_id,
                    "payload": json.dumps(payload, ensure_ascii=False),
                })
                logger.info("alert sent: %s (%d detections)", frame_path, len(detections))

            xack(config.FRAMES_STREAM, GROUP, msg_id)
            mark_processed(frame_path)
