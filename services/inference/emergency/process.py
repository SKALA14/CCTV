# services/inference/emergency/process.py
"""Emergency 프로세스 진입점. fire/pose 스레드를 띄우고 frames 스트림을 소비한다."""

from __future__ import annotations

import logging
import queue
import threading
from collections import deque

import cv2

from config import config
from emergency import aggregator, fire_worker, pose_worker
from redis_client import xack, xreadgroup
from schema import FrameJob, ModelResult, PendingFrame

logger = logging.getLogger(__name__)

CONSUMER = "emergency-worker"


def run() -> None:
    """Emergency 메인 루프."""
    logging.basicConfig(level=logging.INFO, format="%(processName)s [%(levelname)s] %(message)s")

    pending: dict[str, PendingFrame] = {}
    fallen_timestamps: dict[str, deque] = {}
    fire_last_published: dict[tuple[str, str], float] = {}

    result_queue: queue.Queue[ModelResult] = queue.Queue(maxsize=config.RESULT_QUEUE_SIZE)
    model_queues: dict[str, queue.Queue[FrameJob | None]] = {
        "fire": queue.Queue(maxsize=config.MODEL_QUEUE_SIZE),
        "pose": queue.Queue(maxsize=config.MODEL_QUEUE_SIZE),
    }

    threads = [
        threading.Thread(target=fire_worker.run, args=(model_queues["fire"], result_queue),
                         daemon=True, name="fire-thread"),
        threading.Thread(target=pose_worker.run, args=(model_queues["pose"], result_queue),
                         daemon=True, name="pose-thread"),
    ]
    for t in threads:
        t.start()

    logger.info("[emergency] process started")

    try:
        while True:
            try:
                messages = xreadgroup(
                    config.FRAMES_STREAM, config.EMERGENCY_GROUP, CONSUMER,
                    count=10, block_ms=100,
                )
                for msg_id, fields in messages:
                    raw_path = fields.get("frame_path", "")
                    frame_path = raw_path.replace("/frames", config.FRAME_STORAGE_PATH, 1)
                    if not frame_path:
                        xack(config.FRAMES_STREAM, config.EMERGENCY_GROUP, msg_id)
                        continue

                    job = FrameJob(
                        msg_id=msg_id,
                        camera_id=fields.get("camera_id", ""),
                        frame_path=frame_path,
                        timestamp=fields.get("timestamp", ""),
                        frame=cv2.imread(frame_path),
                    )
                    aggregator.dispatch_frame(job, model_queues, pending)

                aggregator.drain_results(result_queue, pending, fallen_timestamps, fire_last_published)
                aggregator.finalize_ready_frames(pending)
            except Exception as e:
                logger.error("[emergency] loop error: %s", e)
    finally:
        for q in model_queues.values():
            q.put(None)
        for t in threads:
            t.join()
