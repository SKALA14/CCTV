# services/inference/dynamic/process.py
"""Dynamic 프로세스: Optical Flow로 움직임 후보를 모아 VLM 호출."""

from __future__ import annotations

import logging
import queue
import threading
import time

import cv2

from config import config
from dynamic import vlm_worker
from dynamic.buffer import DynamicBuffer
from dynamic.optical_flow import OpticalFlowDetector
from redis_client import xack, xreadgroup

logger = logging.getLogger(__name__)

CONSUMER = "dynamic-worker"
VLM_QUEUE_SIZE = 4


def run() -> None:
    """Dynamic 메인 루프."""
    logging.basicConfig(level=logging.INFO, format="%(processName)s [%(levelname)s] %(message)s")

    flow_detector = OpticalFlowDetector()
    buffer = DynamicBuffer()
    buffer_lock = threading.Lock()

    job_queue: queue.Queue[vlm_worker.VLMJob | None] = queue.Queue(maxsize=VLM_QUEUE_SIZE)
    thread = threading.Thread(
        target=vlm_worker.run, args=(job_queue, buffer, buffer_lock),
        daemon=True, name="dynamic-vlm-thread",
    )
    thread.start()

    logger.info("[dynamic] process started")

    try:
        while True:
            try:
                messages = xreadgroup(
                    config.FRAMES_STREAM, config.DYNAMIC_GROUP, CONSUMER,
                    count=1, block_ms=100,
                )
                for msg_id, fields in messages:
                    _handle_message(msg_id, fields, flow_detector, buffer, buffer_lock)

                _flush_expired(buffer, buffer_lock, job_queue)
            except Exception as e:
                logger.error("[dynamic] loop error: %s", e)
                time.sleep(1)   # 지속적 오류(Redis 끊김 등) 시 CPU 폭주 방지 백오프
    finally:
        job_queue.put(None)
        thread.join()


def _handle_message(
    msg_id: str,
    fields: dict,
    flow_detector: OpticalFlowDetector,
    buffer: DynamicBuffer,
    buffer_lock: threading.Lock,
) -> None:
    raw_path = fields.get("frame_path", "")
    frame_path = raw_path.replace("/frames", config.FRAME_STORAGE_PATH, 1)
    camera_id = fields.get("camera_id", "")
    site_id = fields.get("site_id", "")
    timestamp = fields.get("timestamp", "")

    # compound cam_key: VLM worker가 site_id를 알 수 있도록 "{site_id}:{cam_id}" 형태 사용
    # site_id 없는 레거시 메시지는 camera_id 그대로 사용
    cam_key = f"{site_id}:{camera_id}" if site_id else camera_id

    frame = cv2.imread(frame_path) if frame_path else None
    if frame is None:
        xack(config.FRAMES_STREAM, config.DYNAMIC_GROUP, msg_id)
        return

    flow_score = flow_detector.compute(cam_key, frame)
    if flow_score < config.FLOW_THRESHOLD:
        xack(config.FRAMES_STREAM, config.DYNAMIC_GROUP, msg_id)
        return

    with buffer_lock:
        buffer.append(cam_key, msg_id, frame_path, timestamp)


def _flush_expired(
    buffer: DynamicBuffer,
    buffer_lock: threading.Lock,
    job_queue: "queue.Queue[vlm_worker.VLMJob | None]",
) -> None:
    """윈도우 만료된 카메라 후보를 VLM 큐로 보내거나 스킵."""
    with buffer_lock:
        expired = buffer.expired_cameras()
    for cam_id in expired:
        with buffer_lock:
            frames = buffer.pop(cam_id)
            cooldown = buffer.in_cooldown(cam_id)

        if len(frames) < config.GENERAL_MIN_FRAMES:
            logger.info("[dynamic] skip (frames=%d < min=%d): camera=%s",
                        len(frames), config.GENERAL_MIN_FRAMES, cam_id)
            _ack_all(frames)
            continue
        if cooldown:
            logger.info("[dynamic] skip (cooldown): camera=%s", cam_id)
            _ack_all(frames)
            continue

        try:
            job_queue.put_nowait((cam_id, frames))
            with buffer_lock:
                buffer.mark_called(cam_id)
        except queue.Full:
            logger.warning("[dynamic] vlm queue full: camera=%s dropped", cam_id)
            _ack_all(frames)


def _ack_all(frames: list) -> None:
    for msg_id, _, _ in frames:
        xack(config.FRAMES_STREAM, config.DYNAMIC_GROUP, msg_id)
