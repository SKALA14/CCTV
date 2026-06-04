# services/inference/emergency/pose_worker.py
"""PoseYOLO 추론 스레드. input_queue에서 FrameJob을 받아 result_queue로 ModelResult 반환."""

from __future__ import annotations

import logging
import queue

from models.pose import PoseYOLO
from schema import FrameJob, ModelResult

logger = logging.getLogger(__name__)


def run(
    input_queue: "queue.Queue[FrameJob | None]",
    result_queue: "queue.Queue[ModelResult]",
) -> None:
    """pose-thread 진입점."""
    model = PoseYOLO()
    logger.info("[emergency.pose] worker started")

    while True:
        job = input_queue.get()
        if job is None:
            input_queue.task_done()
            break
        try:
            if job.frame is None:
                logger.warning("[emergency.pose] frame=None (파일 없음?): camera=%s path=%s",
                               job.camera_id, job.frame_path)
                detections = []
            else:
                h, w = job.frame.shape[:2]
                detections = model.predict(job.frame, h, w, camera_id=job.camera_id)
                logger.info("[emergency.pose] camera=%s detections=%d frame=%dx%d",
                            job.camera_id, len(detections), w, h)
            result = ModelResult(job.msg_id, "pose", detections)
        except Exception as e:
            logger.error("[emergency.pose] msg_id=%s error: %s", job.msg_id, e)
            result = ModelResult(job.msg_id, "pose", [], str(e))
        result_queue.put(result)
        input_queue.task_done()
