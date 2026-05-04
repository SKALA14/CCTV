'''
모델별 비동기 결과를 msg_id 기준으로 합치고 ACK/VLM 버퍼링 시점을 결정한다.

입력
- dispatch_frame(): FrameJob을 모델별 queue에 fan-out한다.
- drain_results(): result_queue에서 ModelResult를 꺼내 PendingFrame에 누적한다.
- finalize_ready_frames(): 모든 모델 결과 도착 또는 timeout된 PendingFrame을 종료 처리한다.

출력/분기
- route=emergency detection은 emergency.handle_emergency_detection()으로 즉시 알림 처리한다.
- route=general detection이 하나라도 있으면 VLM 후보 버퍼로 넘긴다.
- general 후보가 없으면 ACK를 수행한다.
- timeout 시 도착한 결과만 반영하고 누락 모델은 로그로 남긴 뒤 프레임을 종료한다.
'''

import logging
import queue
import time
from collections import deque

from config import config
from pipelines.s1_types import FrameJob, ModelResult, PendingFrame
from pipelines.s2_ack import ack_frame
from pipelines.s3_annotation import annotate_and_save
from pipelines.s5_emergency import handle_emergency_detection
from pipelines.s6_general import buffer_general_candidate

logger = logging.getLogger(__name__)


def dispatch_frame(
    group: str,
    job: FrameJob,
    model_names: tuple[str, ...],
    model_queues: dict[str, "queue.Queue[FrameJob | None]"],
    pending: dict[str, PendingFrame],
) -> None:
    state = PendingFrame(job=job, started_at=time.monotonic())
    pending[job.msg_id] = state

    for model_name in model_names:
        try:
            model_queues[model_name].put_nowait(job)
            state.expected_models.add(model_name)
        except queue.Full:
            # 모델별 속도 차이로 큐가 밀리면 해당 모델은 이번 프레임을 포기한다.
            logger.warning("%s queue full: msg_id=%s skipped", model_name, job.msg_id)

    if not state.expected_models:
        pending.pop(job.msg_id, None)
        ack_frame(group, job.msg_id, job.frame_path)


def drain_results(
    result_queue: "queue.Queue[ModelResult]",
    pending: dict[str, PendingFrame],
    fallen_timestamps: dict[str, deque],
) -> None:
    while True:
        try:
            result = result_queue.get_nowait()
        except queue.Empty:
            return

        state = pending.get(result.msg_id)
        if state is None:
            logger.debug("late model result ignored: msg_id=%s model=%s", result.msg_id, result.model_name)
            result_queue.task_done()
            continue

        state.received_models.add(result.model_name)
        state.detections.extend(result.detections)

        if result.error:
            logger.warning("model result error: msg_id=%s model=%s error=%s",
                           result.msg_id, result.model_name, result.error)

        for det in result.detections:
            route = det.get("route")
            if route == "general":
                state.has_general_candidate = True
            elif route == "emergency":
                handle_emergency_detection(state, det, fallen_timestamps)

        result_queue.task_done()


def finalize_ready_frames(
    group: str,
    pending: dict[str, PendingFrame],
    buffers: dict[str, deque[tuple[str, str, str]]],
    window_starts: dict[str, float],
) -> None:
    now = time.monotonic()

    for msg_id, state in list(pending.items()):
        completed = state.expected_models <= state.received_models
        timed_out = now - state.started_at >= config.FRAME_RESULT_TIMEOUT_SEC

        if not completed and not timed_out:
            continue

        if timed_out and not completed:
            missing = state.expected_models - state.received_models
            logger.warning("frame model timeout: msg_id=%s missing=%s", msg_id, sorted(missing))

        pending.pop(msg_id, None)
        finalize_frame(group, state, buffers, window_starts)


def finalize_frame(
    group: str,
    state: PendingFrame,
    buffers: dict[str, deque[tuple[str, str, str]]],
    window_starts: dict[str, float],
) -> None:
    job = state.job

    if config.ANNOTATE_FRAMES and state.detections:
        annotate_and_save(job.frame_path, state.detections)

    if state.has_general_candidate:
        buffer_general_candidate(state, buffers, window_starts)
        return

    ack_frame(group, job.msg_id, job.frame_path)
