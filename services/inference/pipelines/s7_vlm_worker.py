'''
VLM 분석 작업을 비동기로 처리하고 general 이벤트를 events 스트림에 발행한다.

입력
- job_queue: VLMJob 또는 종료 신호(None)가 들어오는 queue.
- VLMJob 스키마: (camera_id, [(msg_id, frame_path, timestamp), ...])
- frame_paths 중 최대 config.GENERAL_BUFFER_SIZE장만 VLM에 전달한다.

출력/부수효과
- VLM 결과를 Redis events 스트림에 XADD한다.
- events payload 스키마:
  {camera_id, frame, timestamp, route, anomaly_type, danger_level, description, confidence, source_model}
- VLM 처리 완료 후 VLMJob에 포함된 frames 메시지를 ACK한다.
'''

import logging
import queue
import threading
from pathlib import Path

from config import config
from models.vlm import VLMClient
from pipelines.s2_ack import ack_all
from pipelines.s6_general import VLMJob
from prompts.prompt import get_prompt
from redis_client import xadd

logger = logging.getLogger(__name__)


def vlm_worker(
    group: str,
    job_queue: "queue.Queue[VLMJob | None]",
    last_vlm_call: dict[str, float],
    call_lock: threading.Lock,
) -> None:
    vlm: VLMClient | None = None

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
            result = vlm.analyze(frame_paths, get_prompt(cam_id))

            if result.get("event_type", "normal") != "normal":
                with call_lock:
                    last_vlm_call[cam_id] = 0.0

            xadd(config.EVENTS_STREAM, {
                "camera_id": cam_id,
                "frame": Path(frame_paths[0]).name,
                "timestamp": timestamp,
                "route": "general",
                "anomaly_type": result.get("event_type", "normal"),
                "danger_level": result.get("danger_level", "none"),
                "description": result["description"],
                "confidence": str(result.get("confidence", "")),
                "source_model": "vlm",
            })
            logger.info("event published: camera=%s anomaly_type=%s", cam_id, result.get("event_type", "normal"))
        except Exception:
            logger.exception("VLM worker error: camera=%s", cam_id)
        finally:
            ack_all(group, frames)
            job_queue.task_done()
