'''
route=emergency 탐지 결과를 즉시 alerts 스트림으로 발행하고 낙상 누적 조건을 관리한다.

입력
- PendingFrame: msg_id, camera_id, frame_path, timestamp를 포함한 프레임 상태.
- detection 스키마:
  {route: "emergency", anomaly_type: "fire"|"smoke"|"fallen",
   danger_level: str, description: str, confidence: float, source_model: str}

출력/부수효과
- fire/smoke는 Redis alerts 스트림에 즉시 XADD한다.
- fallen은 camera_id별 시간 윈도우에서 config.FALL_MIN_FRAMES 이상 누적되면 alerts에 XADD한다.
- alerts payload 스키마:
  {camera_id, frame, timestamp, route, anomaly_type, danger_level, description, confidence, source_model}
'''

import time
from collections import deque
from pathlib import Path

from config import config
from pipelines.s1_types import PendingFrame
from redis_client import xadd


def publish_emergency(camera_id: str, frame_path: str, timestamp: str, det: dict) -> None:
    xadd(config.ALERTS_STREAM, {
        "camera_id": camera_id,
        "frame": Path(frame_path).name,
        "timestamp": timestamp,
        "route": det.get("route", "emergency"),
        "anomaly_type": det.get("anomaly_type", "unknown"),
        "danger_level": det.get("danger_level", "critical"),
        "description": det.get("description", "긴급 이상상황 감지"),
        "confidence": str(det.get("confidence", "")),
        "source_model": det.get("source_model", ""),
    })


def handle_fallen(
    fallen_timestamps: dict[str, deque],
    camera_id: str,
    frame_path: str,
    timestamp: str,
    det: dict,
) -> None:
    fallen_timestamps.setdefault(camera_id, deque())

    now = time.time()
    fallen_timestamps[camera_id].append(now)

    cutoff = now - config.FALL_WINDOW_SEC
    while fallen_timestamps[camera_id] and fallen_timestamps[camera_id][0] < cutoff:
        fallen_timestamps[camera_id].popleft()

    if len(fallen_timestamps[camera_id]) >= config.FALL_MIN_FRAMES:
        publish_emergency(camera_id, frame_path, timestamp, det)
        fallen_timestamps[camera_id].clear()


def handle_emergency_detection(
    state: PendingFrame,
    det: dict,
    fallen_timestamps: dict[str, deque],
) -> None:
    anomaly_type = det.get("anomaly_type", "")
    job = state.job

    # 같은 frame/model/type 조합은 중복 결과가 와도 한 번만 알림 처리한다.
    alert_key = f"{job.msg_id}:{det.get('source_model', '')}:{anomaly_type}"
    if alert_key in state.alerted_keys:
        return
    state.alerted_keys.add(alert_key)

    if anomaly_type in ("fire", "smoke"):
        publish_emergency(job.camera_id, job.frame_path, job.timestamp, det)
    elif anomaly_type == "fallen":
        handle_fallen(fallen_timestamps, job.camera_id, job.frame_path, job.timestamp, det)
