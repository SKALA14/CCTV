# services/inference/dynamic/process.py
"""Dynamic 프로세스: Dual-EMA Trigger로 VLM 호출 후보를 선별."""

from __future__ import annotations

import logging
import queue
import threading

import cv2

from config import config
from dynamic import vlm_worker
from dynamic.buffer import DynamicBuffer
from dynamic.optical_flow import FrameFeatureExtractor
from dynamic.trigger import RealtimeTriggerSelector, TriggerConfig
from redis_client import xack, xreadgroup

logger = logging.getLogger(__name__)

CONSUMER = "dynamic-worker"
VLM_QUEUE_SIZE = 4


def run() -> None:
    """Dynamic 메인 루프."""
    logging.basicConfig(level=logging.INFO, format="%(processName)s [%(levelname)s] %(message)s")

    trigger_config = TriggerConfig()
    feature_extractor = FrameFeatureExtractor()
    selectors: dict[str, RealtimeTriggerSelector] = {}
    selector_start_ts: dict[str, float] = {}

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
                    _handle_message(
                        msg_id, fields,
                        feature_extractor, selectors, selector_start_ts, trigger_config,
                        buffer, buffer_lock,
                    )
                _flush_expired(buffer, buffer_lock, job_queue)
            except Exception as e:
                logger.error("[dynamic] loop error: %s", e)
    finally:
        job_queue.put(None)
        thread.join()


def _handle_message(
    msg_id: str,
    fields: dict,
    feature_extractor: FrameFeatureExtractor,
    selectors: dict[str, RealtimeTriggerSelector],
    selector_start_ts: dict[str, float],
    trigger_config: TriggerConfig,
    buffer: DynamicBuffer,
    buffer_lock: threading.Lock,
) -> None:
    raw_path = fields.get("frame_path", "")
    frame_path = raw_path.replace("/frames", config.FRAME_STORAGE_PATH, 1)
    camera_id = fields.get("camera_id", "")
    timestamp = fields.get("timestamp", "")

    frame = cv2.imread(frame_path) if frame_path else None
    if frame is None:
        xack(config.FRAMES_STREAM, config.DYNAMIC_GROUP, msg_id)
        return

    try:
        abs_ts = float(timestamp)
    except (ValueError, TypeError):
        abs_ts = 0.0

    if camera_id not in selector_start_ts:
        selector_start_ts[camera_id] = abs_ts
        selectors[camera_id] = RealtimeTriggerSelector(trigger_config)
    rel_ts = abs_ts - selector_start_ts[camera_id]

    features = feature_extractor.extract(camera_id, frame, rel_ts)
    result = selectors[camera_id].process(features)

    if not result["admitted_trigger"]:
        xack(config.FRAMES_STREAM, config.DYNAMIC_GROUP, msg_id)
        return

    with buffer_lock:
        buffer.append(camera_id, msg_id, frame_path, timestamp)


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
