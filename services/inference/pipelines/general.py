import queue
import threading
import time
import logging
from collections import deque
from pathlib import Path

from config import config
from models.vlm import VLMClient
from models.yolo import GeneralYOLO
from prompts.prompt import get_prompt
from redis_client import xreadgroup, xadd, xack, mark_processed

logger = logging.getLogger(__name__)

GROUP             = "general"
CONSUMER          = "general-worker"
MIN_FRAMES        = 3
BUFFER_SIZE       = 5
WINDOW_SEC        = 10.0
MIN_CALL_INTERVAL = 30.0

# (cam_id, [(msg_id, frame_path, timestamp), ...])
_VLMJob = tuple[str, list[tuple[str, str, str]]]


def _ack_all(frames: list[tuple[str, str, str]]) -> None:
    for msg_id, frame_path, _ in frames:
        xack(config.FRAMES_STREAM, GROUP, msg_id)
        mark_processed(frame_path)


def _vlm_worker(
    job_queue: "queue.Queue[_VLMJob | None]",
    vlm: VLMClient,
    last_vlm_call: dict[str, float],
    call_lock: threading.Lock,
) -> None:
    while True:
        job = job_queue.get()
        if job is None:  # shutdown sentinel
            break

        cam_id, frames = job
        try:
            frame_paths = [fp for _, fp, _ in frames][:BUFFER_SIZE]
            timestamp   = frames[0][2]
            result      = vlm.analyze(frame_paths, get_prompt(cam_id))

            if result.get("event_type", "normal") != "normal":
                with call_lock:
                    last_vlm_call[cam_id] = 0.0  # 이상 감지 → 쿨다운 리셋, 다음 윈도우 즉시 허용

            xadd(config.EVENTS_STREAM, {
                "camera_id":    cam_id,
                "frame":        Path(frame_paths[0]).name,
                "timestamp":    timestamp,
                "anomaly_type": result.get("event_type", "normal"),
                "danger_level": result.get("danger_level", "none"),
                "description":  result["description"],
            })
            logger.info("event published: camera=%s anomaly_type=%s", cam_id, result.get("event_type", "normal"))
        except Exception:
            logger.exception("VLM worker error: camera=%s", cam_id)
        finally:
            _ack_all(frames)
            job_queue.task_done()


def run() -> None:
    yolo = GeneralYOLO()
    vlm  = VLMClient()

    buffers:       dict[str, deque[tuple[str, str, str]]] = {}
    window_starts: dict[str, float]                       = {}
    last_vlm_call: dict[str, float]                       = {}
    call_lock = threading.Lock()

    job_queue: queue.Queue[_VLMJob | None] = queue.Queue(maxsize=8)
    worker = threading.Thread(
        target=_vlm_worker, args=(job_queue, vlm, last_vlm_call, call_lock), daemon=True,
    )
    worker.start()
    logger.info("general pipeline started (async VLM worker)")

    try:
        while True:
            messages = xreadgroup(config.FRAMES_STREAM, GROUP, CONSUMER)

            for msg_id, fields in messages:
                frame_path = fields.get("frame_path", "")
                camera_id  = fields.get("camera_id", config.CAMERA_ID)
                timestamp  = fields.get("timestamp", "")

                if yolo.predict(frame_path):
                    if camera_id not in window_starts:
                        window_starts[camera_id] = time.time()
                    buffers.setdefault(camera_id, deque()).append((msg_id, frame_path, timestamp))
                else:
                    xack(config.FRAMES_STREAM, GROUP, msg_id)
                    mark_processed(frame_path)

            now = time.time()
            for cam_id, ws in list(window_starts.items()):
                if now - ws < WINDOW_SEC:
                    continue

                buf = buffers.pop(cam_id, deque())
                del window_starts[cam_id]

                if len(buf) < MIN_FRAMES:
                    logger.debug(
                        "오탐 판정: camera=%s window 내 %d프레임 (최소 %d 미달), VLM 스킵",
                        cam_id, len(buf), MIN_FRAMES,
                    )
                    _ack_all(list(buf))
                    continue

                with call_lock:
                    elapsed = now - last_vlm_call.get(cam_id, 0.0)
                if elapsed < MIN_CALL_INTERVAL:
                    logger.debug("쿨다운 중: camera=%s, VLM 스킵", cam_id)
                    _ack_all(list(buf))
                    continue

                try:
                    job_queue.put_nowait((cam_id, list(buf)))
                    with call_lock:
                        last_vlm_call[cam_id] = now
                except queue.Full:
                    logger.warning("job_queue 가득 참: camera=%s job 드롭", cam_id)
                    _ack_all(list(buf))
    finally:
        job_queue.put(None)
        worker.join()
