# "emergency" Consumer Group으로 프레임을 읽어 YOLO 추론 후 즉시 알람을 발행하는 프로세스.
# 정의: run() — XREADGROUP 루프, EmergencyYOLO.predict 호출, 탐지 시 XADD(alerts).
# 입력: Redis Stream "frames" 메시지 — {frame_path, camera_id, timestamp}.
# 출력: 긴급 상황 시 "alerts" 스트림에 XADD; 항상 XACK 후 mark_processed 호출.

import json
import logging
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from config import config
from models.yolo import EmergencyYOLO
from redis_client import xreadgroup, xadd, xack, mark_processed

logger = logging.getLogger(__name__)

GROUP    = "emergency"
CONSUMER = "emergency-worker"
FALL_CONFIRM_FRAMES = 5  # 몇 프레임 연속 감지 시 알람 발송


def run():
    model = EmergencyYOLO()

    # track_id → 연속 넘어짐 프레임 수
    fall_counter: dict[int, int] = defaultdict(int)
    # 이미 알람을 보낸 track_id 집합 (중복 방지)
    alerted_ids: set[int] = set()

    logger.info("emergency pipeline started")

    while True:
        messages = xreadgroup(config.FRAMES_STREAM, GROUP, CONSUMER)

        for msg_id, fields in messages:
            frame_path = fields.get("frame_path", "")
            camera_id  = fields.get("camera_id", config.CAMERA_ID)

            if not frame_path: # 경로가 존재하지 않는 경우 
                xack(config.FRAMES_STREAM, GROUP, msg_id)
                continue

            detections = model.predict(frame_path)

            # 이번 프레임에서 넘어진 것으로 판정된 track_id 집합
            fallen_ids_this_frame: set[int] = set()

            for det in detections:
                anomaly_type = det.get("anomaly_type", "")
                track_id     = det.get("track_id")

                if anomaly_type in ("fire", "smoke"):
                    xadd(config.ALERTS_STREAM, {
                        "camera_id": camera_id,
                        "frame": Path(frame_path).name,
                        "timestamp": str(datetime.now()),
                        "anomaly_type": anomaly_type,
                    })
                    continue

                if anomaly_type == "fallen" and track_id is not None:
                    fallen_ids_this_frame.add(track_id)
                    fall_counter[track_id] += 1

                    if (
                        fall_counter[track_id] >= FALL_CONFIRM_FRAMES
                        and track_id not in alerted_ids
                    ):
                        xadd(config.ALERTS_STREAM, {
                            "camera_id": camera_id,
                            "frame": Path(frame_path).name,
                            "timestamp": str(datetime.now()),
                            "anomaly_type": anomaly_type,
                        })
                        alerted_ids.add(track_id)
                        logger.info("fall alert: track_id=%s frame=%s", track_id, frame_path)

            gone_ids = set(fall_counter) - fallen_ids_this_frame
            for tid in gone_ids:
                del fall_counter[tid]
                alerted_ids.discard(tid) 

            xack(config.FRAMES_STREAM, GROUP, msg_id)
            mark_processed(frame_path)
