# services/inference/dynamic/vlm_worker.py
"""Dynamic 후보 프레임 묶음을 VLM으로 분석해 events stream에 발행한다."""

from __future__ import annotations

import logging
import queue
import threading
import time

from config import config
from dynamic.buffer import Candidate, DynamicBuffer
from redis_client import xack, xadd
from vlm.client import VLMClient, render_prompt
from vlm.gate import should_publish, mark_published

logger = logging.getLogger(__name__)

# (cam_key, [(msg_id, frame_path, timestamp), ...])
# cam_key = "{site_id}:{cam_id}" 또는 레거시 "{cam_id}"
VLMJob = tuple[str, list[Candidate]]


def run(
    job_queue: "queue.Queue[VLMJob | None]",
    buffer: DynamicBuffer,
    buffer_lock: threading.Lock,
) -> None:
    """dynamic VLM 스레드 진입점."""
    vlm: VLMClient | None = None
    logger.info("[dynamic.vlm] worker started")

    while True:
        job = job_queue.get()
        if job is None:
            job_queue.task_done()
            break

        cam_key, frames = job
        try:
            if vlm is None:
                vlm = VLMClient()

            # compound key 분리: "{site_id}:{cam_id}" → site_id, cam_id
            if ":" in cam_key:
                site_id, cam_id = cam_key.split(":", 1)
            else:
                site_id, cam_id = "", cam_key

            frame_paths = [fp for _, fp, _ in frames][:config.GENERAL_BUFFER_SIZE]
            timestamp   = frames[0][2]

            # render_prompt에 compound key를 넘기면 camera_instruction/{site_id}/{cam_id}
            # 및 camera/{site_id}/{cam_id}:zone 키를 올바르게 조회
            prompt, categories = render_prompt(config.DYNAMIC_PROMPT_FILE, cam_key)

            logger.info("[dynamic.vlm] → VLM 호출: site=%s camera=%s frames=%d",
                        site_id, cam_id, len(frame_paths))
            t0 = time.monotonic()
            result = vlm.analyze(frame_paths, prompt, categories)
            elapsed = time.monotonic() - t0

            if result.get("result") == "anomaly":
                if not should_publish(result, cam_key, "dynamic"):
                    logger.info("[dynamic.vlm] ← gate filtered (%.1fs): camera=%s",
                                elapsed, cam_id)
                else:
                    xadd(config.EVENTS_STREAM, {
                        "camera_id":    cam_id,
                        "site_id":      site_id,
                        "track":        "dynamic",
                        "anomaly_type":   result.get("anomaly_type", "normal"),
                        "danger_level":   result.get("danger_level", "none"),
                        "description":    result.get("description", ""),
                        "timestamp":      timestamp,
                        "frame_path":     frame_paths[0],
                    }, maxlen=config.EVENTS_MAXLEN)
                    mark_published(cam_key, "dynamic")
                    with buffer_lock:
                        buffer.reset_cooldown(cam_key)
                    logger.info("[dynamic.vlm] ← anomaly (%.1fs): site=%s camera=%s type=%s",
                                elapsed, site_id, cam_id, result.get("anomaly_type"))
            else:
                logger.info("[dynamic.vlm] ← normal (%.1fs): camera=%s", elapsed, cam_id)
        except Exception as e:
            logger.error("[dynamic.vlm] camera=%s error: %s", cam_key, e)
        finally:
            for msg_id, _, _ in frames:
                xack(config.FRAMES_STREAM, config.DYNAMIC_GROUP, msg_id)
            job_queue.task_done()
