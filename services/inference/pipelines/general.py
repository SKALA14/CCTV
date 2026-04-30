# "general" Consumer Group으로 프레임을 읽어 버퍼링 후 VLM 분석 결과를 발행하는 프로세스.
# 정의: run() — GeneralYOLO로 anomaly 트리거 감지, time window 내 프레임 버퍼링, VLM 호출.
# 입력: Redis Stream "frames" 메시지 — {frame_path, camera_id, timestamp}.
# 출력: "events" 스트림에 XADD — {camera_id, description, is_anomaly, timestamp}; XACK 후 mark_processed 호출.

import time
import logging
from collections import deque
from datetime import datetime

from config import config
from models.vlm import VLMClient
from models.yolo import GeneralYOLO
from prompts.target_event_prompts import get_prompt_for_event
from redis_client import xreadgroup, xadd, xack, mark_processed
from utils.channel_target_event import resolve_target_event

logger = logging.getLogger(__name__)

GROUP       = "general"
CONSUMER    = "general-worker"
MIN_FRAMES  = 3       # window 내 최소 anomaly 프레임 수 (미달 시 오탐으로 간주)
BUFFER_SIZE = 5       # VLM에 넘길 최대 프레임 수
WINDOW_SEC  = 5.0     # anomaly 트리거 후 VLM 호출까지 time window (초)


def run():
    yolo = GeneralYOLO()
    vlm  = VLMClient()

    buffer: deque[tuple[str, str, str]] = deque()
    window_start: float | None = None  # 첫 anomaly 감지 시각

    logger.info("general pipeline started")

    while True:
        messages = xreadgroup(config.FRAMES_STREAM, GROUP, CONSUMER)

        for msg_id, fields in messages:
            frame_path = fields.get("frame_path", "")
            camera_id  = fields.get("camera_id", config.CAMERA_ID)

            detections  = yolo.predict(frame_path)
            has_anomaly = any(d.get("class") == "person" for d in detections)

            if has_anomaly:
                if window_start is None:
                    window_start = time.time()  # 첫 트리거 시각 기록
                buffer.append((msg_id, frame_path, camera_id))
            else:
                xack(config.FRAMES_STREAM, GROUP, msg_id)
                mark_processed(frame_path)

        # time window 초과 시 VLM 호출 (오탐 방지: 최소 프레임 수 이상일 때만)
        if window_start is not None and time.time() - window_start >= WINDOW_SEC:
            if len(buffer) >= MIN_FRAMES:
                frame_paths  = [fp for _, fp, _ in buffer][:BUFFER_SIZE]
                camera_id    = buffer[-1][2]
                target_event = resolve_target_event(camera_id)
                prompt       = get_prompt_for_event(target_event, camera_id)
                result       = vlm.analyze(frame_paths, prompt)

                xadd(config.EVENTS_STREAM, {
                    "camera_id":   camera_id,
                    "frame": frame_paths[0],
                    "timestamp": str(datetime.now()),
                    "anomaly_type":  result.get("event_type", "normal"),
                    "danger_level": result.get("danger_level", "normal"),
                    "description": result["description"],
                })
                logger.info("event published: camera=%s anomaly_type=%s", camera_id, result.get("event_type", "normal"))
            else:
                logger.debug("오탐 판정: window 내 %d프레임 (최소 %d 미달), VLM 스킵", len(buffer), MIN_FRAMES)

            # VLM 호출 여부와 무관하게 buffer 전체 ACK
            for msg_id, frame_path, _ in buffer:
                xack(config.FRAMES_STREAM, GROUP, msg_id)
                mark_processed(frame_path)

            buffer.clear()
            window_start = None
