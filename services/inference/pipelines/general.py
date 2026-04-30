# "general" Consumer Group으로 프레임을 읽어 버퍼링 후 VLM 분석 결과를 발행하는 프로세스.
# 정의: run() — GeneralYOLO로 anomaly 트리거 감지, time window 내 프레임 버퍼링, VLM 호출.
# 입력: Redis Stream "frames" 메시지 — {frame_path, camera_id, timestamp}.
# 출력: "events" 스트림에 XADD — {camera_id, description, is_anomaly, timestamp}; XACK 후 mark_processed 호출.

import time
import logging
from collections import deque
from datetime import datetime
from pathlib import Path

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


def _flush_camera(
    cam_id: str,
    buf: deque[tuple[str, str]],
    vlm: VLMClient,
) -> None:
    if len(buf) >= MIN_FRAMES:
        frame_paths  = [fp for _, fp in buf][:BUFFER_SIZE]
        target_event = resolve_target_event(cam_id)
        prompt       = get_prompt_for_event(target_event, cam_id)
        result       = vlm.analyze(frame_paths, prompt)

        xadd(config.EVENTS_STREAM, {
            "camera_id":   cam_id,
            "frame":       Path(frame_paths[0]).name,
            "timestamp":   str(datetime.now()),
            "anomaly_type":  result.get("event_type", "normal"),
            "danger_level":  result.get("danger_level", "none"),
            "description":   result["description"],
        })
        logger.info("event published: camera=%s anomaly_type=%s", cam_id, result.get("event_type", "normal"))
    else:
        logger.debug("오탐 판정: camera=%s window 내 %d프레임 (최소 %d 미달), VLM 스킵", cam_id, len(buf), MIN_FRAMES)

    for msg_id, frame_path in buf:
        xack(config.FRAMES_STREAM, GROUP, msg_id)
        mark_processed(frame_path)


def run():
    yolo = GeneralYOLO()
    vlm  = VLMClient()

    buffers:      dict[str, deque[tuple[str, str]]] = {}
    window_starts: dict[str, float]                 = {}

    logger.info("general pipeline started")

    while True:
        messages = xreadgroup(config.FRAMES_STREAM, GROUP, CONSUMER)

        for msg_id, fields in messages:
            frame_path = fields.get("frame_path", "")
            camera_id  = fields.get("camera_id", config.CAMERA_ID)

            if yolo.predict(frame_path):
                if camera_id not in window_starts:
                    window_starts[camera_id] = time.time()
                buffers.setdefault(camera_id, deque()).append((msg_id, frame_path))
            else:
                xack(config.FRAMES_STREAM, GROUP, msg_id)
                mark_processed(frame_path)

        now = time.time()
        for cam_id, ws in list(window_starts.items()):
            if now - ws >= WINDOW_SEC:
                _flush_camera(cam_id, buffers.pop(cam_id, deque()), vlm)
                del window_starts[cam_id]
