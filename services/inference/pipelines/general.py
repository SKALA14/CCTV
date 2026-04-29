# "general" Consumer Group으로 프레임을 읽어 버퍼링 후 VLM 분석 결과를 발행하는 프로세스.
# 정의: run() — XREADGROUP 루프, 프레임을 버퍼에 누적, VLM_BUFFER_SIZE 도달 시 vlm.analyze 호출.
# 입력: Redis Stream "frames" 메시지 — {frame_path, camera_id, timestamp}.
# 출력: "events" 스트림에 XADD — {camera_id, description, is_anomaly, timestamp}; XACK 후 mark_processed 호출.

import time
import logging
from pathlib import Path
from collections import deque
from datetime import datetime

from config import config
from models import vlm
from utils.builder import build_output_payload
from redis_client import xreadgroup, xadd, xack, mark_processed

logger = logging.getLogger(__name__)

GROUP = "general"
CONSUMER = "general-worker"


def run():
    # (msg_id, frame_path, camera_id) 튜플을 누적
    buffer: deque[tuple[str, str, str]] = deque()
    logger.info("general pipeline started")

    while True:
        messages = xreadgroup(config.FRAMES_STREAM, GROUP, CONSUMER)

        for msg_id, fields in messages:
            frame_path = fields.get("frame_path", "")
            camera_id = fields.get("camera_id", config.CAMERA_ID)
            buffer.append((msg_id, frame_path, camera_id))

        if len(buffer) < config.VLM_BUFFER_SIZE:
            continue

        frame_paths = [fp for _, fp, _ in buffer]
        camera_id = buffer[-1][2]

        result = vlm.analyze(frame_paths, camera_id)

        xadd(config.EVENTS_STREAM, {
            "camera_id": camera_id,
            "description": result["description"],
            "is_anomaly": str(result["is_anomaly"]),
            "timestamp": str(time.time()),
        })
        logger.info("event published: camera=%s anomaly=%s", camera_id, result["is_anomaly"])

        for msg_id, frame_path, _ in buffer:
            xack(config.FRAMES_STREAM, GROUP, msg_id)
            mark_processed(frame_path)

        buffer.clear()
