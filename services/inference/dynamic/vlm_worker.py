# services/inference/dynamic/vlm_worker.py
"""Dynamic 후보 프레임 묶음을 VLM으로 분석해 events stream에 발행한다."""

from __future__ import annotations

import logging
import queue
import threading

from config import config
from dynamic.buffer import Candidate, DynamicBuffer
from redis_client import xack, xadd
from vlm.client import VLMClient, load_prompt

logger = logging.getLogger(__name__)

# (camera_id, [(msg_id, frame_path, timestamp), ...])
VLMJob = tuple[str, list[Candidate]]


def run(
    job_queue: "queue.Queue[VLMJob | None]",
    buffer: DynamicBuffer,
    buffer_lock: threading.Lock,
) -> None:
    """dynamic VLM 스레드 진입점."""
    vlm: VLMClient | None = None
    prompt = load_prompt(config.DYNAMIC_PROMPT_FILE)
    logger.info("[dynamic.vlm] worker started")

    while True:
        job = job_queue.get()
        if job is None:
            job_queue.task_done()
            break

        cam_id, frames = job
        try:
            if vlm is None:
                vlm = VLMClient()

            frame_paths = [fp for _, fp, _ in frames][:config.GENERAL_BUFFER_SIZE]
            timestamp = frames[0][2]
            result = vlm.analyze(frame_paths, prompt)

            if result.get("result") != "normal":
                with buffer_lock:
                    buffer.reset_cooldown(cam_id)
                xadd(config.EVENTS_STREAM, {
                    "camera_id": cam_id,
                    "track": "dynamic",
                    "anomaly_type": result.get("anomaly_type", "normal"),
                    "danger_level": result.get("danger_level", "none"),
                    "description": result.get("description", ""),
                    "timestamp": timestamp,
                    "frame_path": frame_paths[0],
                })
                logger.info("[dynamic.vlm] event published: camera=%s type=%s",
                            cam_id, result.get("anomaly_type"))
            else:
                logger.debug("[dynamic.vlm] normal: camera=%s", cam_id)
        except Exception as e:
            logger.error("[dynamic.vlm] camera=%s error: %s", cam_id, e)
        finally:
            for msg_id, _, _ in frames:
                xack(config.FRAMES_STREAM, config.DYNAMIC_GROUP, msg_id)
            job_queue.task_done()
