# services/inference/emergency/aggregator.py
"""Emergency 모델 결과 취합 및 alerts stream 발행."""

from __future__ import annotations

import logging
import queue
import time
from collections import deque
from pathlib import Path

import cv2
import numpy as np

from config import config
from redis_client import xack, xadd
from schema import FrameJob, ModelResult, PendingFrame

logger = logging.getLogger(__name__)

EXPECTED_MODELS = ("fire", "pose")


def dispatch_frame(
    job: FrameJob,
    model_queues: dict[str, "queue.Queue[FrameJob | None]"],
    pending: dict[str, PendingFrame],
) -> None:
    """FrameJob을 fire/pose 큐에 fan-out하고 pending에 등록."""
    state = PendingFrame(job=job, started_at=time.monotonic())
    pending[job.msg_id] = state

    for name in EXPECTED_MODELS:
        try:
            model_queues[name].put_nowait(job)
            state.expected_models.add(name)
        except queue.Full:
            logger.warning("[emergency] %s queue full: msg_id=%s skipped", name, job.msg_id)

    if not state.expected_models:
        pending.pop(job.msg_id, None)
        xack(config.FRAMES_STREAM, config.EMERGENCY_GROUP, job.msg_id)


def drain_results(
    result_queue: "queue.Queue[ModelResult]",
    pending: dict[str, PendingFrame],
    fallen_timestamps: dict[str, deque],
    fire_last_published: dict[tuple[str, str], float],
    fire_frame_buffers: dict[str, deque],
) -> None:
    """result_queue를 비우며 PendingFrame에 누적하고 emergency 분기 처리."""
    while True:
        try:
            result = result_queue.get_nowait()
        except queue.Empty:
            return

        state = pending.get(result.msg_id)
        if state is None:
            result_queue.task_done()
            continue

        state.received_models.add(result.model_name)
        state.detections.extend(result.detections)

        if result.error:
            logger.warning("[emergency] %s msg_id=%s error: %s",
                           result.model_name, result.msg_id, result.error)

        for det in result.detections:
            _handle_detection(state, det, fallen_timestamps, fire_last_published, fire_frame_buffers)

        result_queue.task_done()


def finalize_ready_frames(pending: dict[str, PendingFrame]) -> None:
    """모든 모델 완료 또는 timeout된 프레임을 ACK 처리."""
    now = time.monotonic()
    for msg_id, state in list(pending.items()):
        completed = state.expected_models <= state.received_models
        timed_out = now - state.started_at >= config.FRAME_RESULT_TIMEOUT_SEC
        if not completed and not timed_out:
            continue
        if timed_out and not completed:
            missing = state.expected_models - state.received_models
            logger.warning("[emergency] timeout msg_id=%s missing=%s", msg_id, sorted(missing))
        pending.pop(msg_id, None)
        xack(config.FRAMES_STREAM, config.EMERGENCY_GROUP, state.job.msg_id)


def _handle_detection(
    state: PendingFrame,
    det: dict,
    fallen_timestamps: dict[str, deque],
    fire_last_published: dict[tuple[str, str], float],
    fire_frame_buffers: dict[str, deque],
) -> None:
    anomaly_type = det.get("anomaly_type", "")
    job = state.job
    key = f"{job.msg_id}:{det.get('source_model', '')}:{anomaly_type}"
    if key in state.alerted_keys:
        return
    state.alerted_keys.add(key)

    if anomaly_type in ("fire", "smoke"):
        _handle_fire(fire_last_published, job, det, fire_frame_buffers)
    elif anomaly_type == "fallen":
        _handle_fallen(fallen_timestamps, job, det)


def _pixel_motion_ok(frame: np.ndarray, bbox: list[float], buf: deque) -> bool:
    """bbox 영역의 픽셀 변화량이 임계값 이상이면 True(실제 화재). 포스터 등 정적 이미지 오탐 제거."""
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    scale = 0.25
    small = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    buf.append(small)

    if len(buf) < 2:
        logger.info("[emergency] 화재 픽셀 차분 버퍼 준비 중 (첫 프레임 수집)")
        return False

    x1, y1, x2, y2 = (int(c * scale) for c in bbox[:4])
    h, w = small.shape
    x1, y1 = max(0, x1), max(0, y1)
    x2, y2 = min(w, x2), min(h, y2)
    if x2 <= x1 or y2 <= y1:
        return True

    curr = small[y1:y2, x1:x2].astype(np.float32)
    prev = buf[-2][y1:y2, x1:x2].astype(np.float32)
    if curr.shape != prev.shape:
        return True

    diff = float(np.mean(np.abs(curr - prev)))
    ok = diff >= config.FIRE_PIXEL_DIFF_THRESH
    if not ok:
        logger.info(
            "[emergency] 화재 픽셀 변화 기각: diff=%.2f < threshold=%.2f (정적 이미지 판정)",
            diff, config.FIRE_PIXEL_DIFF_THRESH,
        )
    return ok


def _handle_fire(
    fire_last_published: dict[tuple[str, str], float],
    job: FrameJob,
    det: dict,
    fire_frame_buffers: dict[str, deque],
) -> None:
    """FIRE_DEDUP_SEC 안에 같은 (camera, type) 1회만 발행.

    픽셀 차분 필터(FIRE_PIXEL_DIFF_THRESH)는 YOLO가 정적 이미지를 탐지하는
    오탐을 줄이기 위해 설계됐지만, 실제 화재 영상에서도 연속 프레임 간
    차분이 임계값 이하일 경우 미탐을 유발한다.
    현재는 YOLO confidence(FIRE_CONF=0.15)만으로 필터링하며,
    픽셀 차분은 참고용 로그만 남긴다.
    """
    bbox = det.get("bbox")
    if job.frame is not None and bbox and config.FIRE_PIXEL_DIFF_THRESH > 0:
        fire_frame_buffers.setdefault(job.camera_id, deque(maxlen=config.FIRE_PIXEL_HISTORY))
        ok = _pixel_motion_ok(job.frame, bbox, fire_frame_buffers[job.camera_id])
        if not ok:
            logger.info("[emergency] 픽셀 차분 미달 (참고용, 탐지는 계속): camera=%s", job.camera_id)
            # FIRE_PIXEL_DIFF_THRESH=0 이면 이 블록 자체 진입 안 함 → 필터 완전 비활성

    key = (job.camera_id, det.get("anomaly_type", ""))
    now = time.time()
    if now - fire_last_published.get(key, 0.0) < config.FIRE_DEDUP_SEC:
        return
    fire_last_published[key] = now
    _publish_emergency(job, det)


def _publish_emergency(job: FrameJob, det: dict) -> None:
    logger.warning("[emergency] alerts 발행: camera=%s type=%s", job.camera_id, det.get("anomaly_type"))
    xadd(config.ALERTS_STREAM, {
        "camera_id": job.camera_id,
        "anomaly_type": det.get("anomaly_type", "unknown"),
        "danger_level": det.get("danger_level", "critical"),
        "description": det.get("description", "긴급 이상상황 감지"),
        "confidence": str(det.get("confidence", "")),
        "timestamp": job.timestamp,
        "frame_path": job.frame_path,
    }, maxlen=config.ALERTS_MAXLEN)
    # alerts 스트림 발행만 담당 (WebSocket toast + Slack 알림용).
    # DB 저장은 VLM(events 스트림)이 담당하므로 dedup 키를 설정하지 않는다.


def _handle_fallen(
    fallen_timestamps: dict[str, deque],
    job: FrameJob,
    det: dict,
) -> None:
    """camera별 윈도우에서 FALL_MIN_FRAMES 이상 누적되면 alerts 발행."""
    fallen_timestamps.setdefault(job.camera_id, deque())
    now = time.time()
    fallen_timestamps[job.camera_id].append(now)

    cutoff = now - config.FALL_WINDOW_SEC
    while fallen_timestamps[job.camera_id] and fallen_timestamps[job.camera_id][0] < cutoff:
        fallen_timestamps[job.camera_id].popleft()

    count = len(fallen_timestamps[job.camera_id])
    logger.info("[emergency] 낙상 누적: camera=%s count=%d/%d",
                job.camera_id, count, config.FALL_MIN_FRAMES)
    if count >= config.FALL_MIN_FRAMES:
        _publish_emergency(job, det)
        fallen_timestamps[job.camera_id].clear()
