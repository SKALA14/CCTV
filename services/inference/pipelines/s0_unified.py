'''
Redis frames 스트림을 읽어 모델별 worker에 분배하고 결과 취합 루프를 실행한다.

입력
- Redis frames stream 메시지: {frame_path: str, camera_id: str, timestamp: str}
- Redis msg_id를 그대로 FrameJob.msg_id로 사용한다.

내부 전달
- FrameJob을 fire/pose/general 모델 queue에 fan-out한다.
- 각 모델 worker는 ModelResult를 result_queue로 반환한다.
- aggregator는 msg_id 기준으로 ModelResult를 합친다.

출력/부수효과
- route=emergency 결과는 alerts stream으로 즉시 발행된다.
- route=general 결과는 VLM 후보 버퍼를 거쳐 events stream으로 발행된다.
- 모든 모델 완료 또는 timeout 후 Redis frames 메시지를 ACK한다.
'''

import logging
import queue
import threading
from collections import deque
from typing import Callable

from config import config
from models.fire import FireYOLO
from models.general import GeneralYOLO
from models.pose import PoseYOLO
from pipelines.s1_types import FrameJob, ModelResult, PendingFrame
from pipelines.s2_ack import ack_frame
from pipelines.s4_model_worker import model_worker
from pipelines.s6_general import VLMJob, handle_general_windows
from pipelines.s7_vlm_worker import vlm_worker
from pipelines.s8_aggregator import dispatch_frame, drain_results, finalize_ready_frames
from redis_client import xreadgroup

logger = logging.getLogger(__name__)

GROUP = config.UNIFIED_GROUP
CONSUMER = "unified-worker"
MODEL_NAMES = ("fire", "pose", "general")


def _start_model_workers(
    model_queues: dict[str, "queue.Queue[FrameJob | None]"],
    result_queue: "queue.Queue[ModelResult]",
) -> list[threading.Thread]:
    model_specs: dict[str, Callable[[], object]] = {
        "fire": FireYOLO,
        "pose": PoseYOLO,
        "general": GeneralYOLO,
    }

    workers = [
        threading.Thread(
            target=model_worker,
            args=(name, model_specs[name], model_queues[name], result_queue),
            daemon=True,
            name=f"{name}-worker",
        )
        for name in MODEL_NAMES
    ]
    for worker in workers:
        worker.start()
    return workers


def run() -> None:
    pending: dict[str, PendingFrame] = {}
    fallen_timestamps: dict[str, deque] = {}
    buffers: dict[str, deque[tuple[str, str, str]]] = {}
    window_starts: dict[str, float] = {}
    last_vlm_call: dict[str, float] = {}
    call_lock = threading.Lock()

    result_queue: queue.Queue[ModelResult] = queue.Queue(maxsize=config.RESULT_QUEUE_SIZE)
    model_queues: dict[str, queue.Queue[FrameJob | None]] = {
        name: queue.Queue(maxsize=config.MODEL_QUEUE_SIZE)
        for name in MODEL_NAMES
    }
    model_workers = _start_model_workers(model_queues, result_queue)

    vlm_queue: queue.Queue[VLMJob | None] = queue.Queue(maxsize=config.VLM_QUEUE_SIZE)
    vlm_thread = threading.Thread(
        target=vlm_worker,
        args=(GROUP, vlm_queue, last_vlm_call, call_lock),
        daemon=True,
        name="vlm-worker",
    )
    vlm_thread.start()
    logger.info("unified pipeline started")

    try:
        while True:
            messages = xreadgroup(config.FRAMES_STREAM, GROUP, CONSUMER, count=10, block_ms=100)

            for msg_id, fields in messages:
                frame_path = fields.get("frame_path", "")
                if not frame_path:
                    ack_frame(GROUP, msg_id, frame_path)
                    continue

                job = FrameJob(
                    msg_id=msg_id,
                    camera_id=fields.get("camera_id", config.CAMERA_ID),
                    frame_path=frame_path,
                    timestamp=fields.get("timestamp", ""),
                )
                dispatch_frame(GROUP, job, MODEL_NAMES, model_queues, pending)

            drain_results(result_queue, pending, fallen_timestamps)
            finalize_ready_frames(GROUP, pending, buffers, window_starts)
            handle_general_windows(GROUP, buffers, window_starts, last_vlm_call, call_lock, vlm_queue)
    finally:
        for q in model_queues.values():
            q.put(None)
        for worker in model_workers:
            worker.join()

        vlm_queue.put(None)
        vlm_thread.join()
