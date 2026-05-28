'''
route=general 후보 프레임을 카메라별 버퍼에 모으고 VLM 호출 조건을 관리한다.

입력
- PendingFrame: route=general detection을 포함한 프레임 상태.
- buffers: camera_id별 VLM 후보 프레임 deque.
- VLMJob 스키마: (camera_id, [(msg_id, frame_path, timestamp), ...])

출력/분기
- 후보 프레임은 camera_id별 버퍼에 저장한다.
- config.GENERAL_WINDOW_SEC 이후 최소 프레임 수를 만족하면 vlm_queue에 VLMJob을 넣는다.
- 최소 프레임 미달, 쿨다운, VLM queue full이면 해당 후보 프레임들을 ACK 처리한다.
'''

import logging
import queue
import threading
import time
from collections import deque

from config import config
from pipelines.s1_types import PendingFrame
from pipelines.s2_ack import ack_all

logger = logging.getLogger(__name__)

# (cam_id, [(msg_id, frame_path, timestamp), ...])
VLMJob = tuple[str, list[tuple[str, str, str]]]


def buffer_general_candidate(
    state: PendingFrame,
    buffers: dict[str, deque[tuple[str, str, str]]],
    window_starts: dict[str, float],
) -> None:
    job = state.job
    if job.camera_id not in window_starts:
        window_starts[job.camera_id] = time.time()
    buffers.setdefault(job.camera_id, deque()).append((job.msg_id, job.frame_path, job.timestamp))


def handle_general_windows(
    group: str,
    buffers: dict[str, deque[tuple[str, str, str]]],
    window_starts: dict[str, float],
    last_vlm_call: dict[str, float],
    call_lock: threading.Lock,
    vlm_queue: "queue.Queue[VLMJob | None]",
) -> None:
    now = time.time()

    for cam_id, ws in list(window_starts.items()):
        if now - ws < config.GENERAL_WINDOW_SEC:
            continue

        buf = buffers.pop(cam_id, deque())
        del window_starts[cam_id]

        if len(buf) < config.GENERAL_MIN_FRAMES:
            logger.debug(
                "오탐 판정: camera=%s window 내 %d프레임 (최소 %d 미달), VLM 스킵",
                cam_id, len(buf), config.GENERAL_MIN_FRAMES,
            )
            ack_all(group, list(buf))
            continue

        with call_lock:
            elapsed = now - last_vlm_call.get(cam_id, 0.0)
        if elapsed < config.GENERAL_MIN_CALL_INTERVAL:
            logger.debug("쿨다운 중: camera=%s, VLM 스킵", cam_id)
            ack_all(group, list(buf))
            continue

        try:
            vlm_queue.put_nowait((cam_id, list(buf)))
            with call_lock:
                last_vlm_call[cam_id] = now
        except queue.Full:
            logger.warning("vlm queue full: camera=%s job dropped", cam_id)
            ack_all(group, list(buf))
