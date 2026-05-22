# services/inference/static/vlm_worker.py
"""Static VLM 분석 — 카메라별 최신 1프레임으로 정적 상태를 평가한다."""

from __future__ import annotations

import asyncio
import logging
import os
import time
from pathlib import Path

from config import config
from redis_client import get_client, xadd
from vlm.client import VLMClient

logger = logging.getLogger(__name__)


def list_active_cameras() -> list[str]:
    """Redis camera:*:source_url 키에서 등록된 카메라 id 목록을 반환."""
    cameras = []
    for key in get_client().scan_iter(match="camera:*:source_url"):
        parts = key.split(":")
        if len(parts) == 3:
            cameras.append(parts[1])
    return sorted(cameras)


def latest_frame_path(camera_id: str) -> str | None:
    """카메라 디렉토리에서 가장 최근에 수정된 JPEG 경로 반환."""
    cam_dir = Path(config.FRAME_STORAGE_PATH) / camera_id
    if not cam_dir.exists():
        return None
    latest: tuple[float, str] | None = None
    for entry in os.scandir(cam_dir):
        if not entry.is_file() or not entry.name.lower().endswith((".jpg", ".jpeg")):
            continue
        mtime = entry.stat().st_mtime
        if latest is None or mtime > latest[0]:
            latest = (mtime, entry.path)
    return latest[1] if latest else None


async def analyze_camera(vlm: VLMClient, prompt: str, camera_id: str) -> None:
    """단일 카메라에 대한 static VLM 호출. 이상 응답이면 events 발행."""
    frame_path = latest_frame_path(camera_id)
    if frame_path is None:
        return

    loop = asyncio.get_running_loop()
    try:
        result = await loop.run_in_executor(None, vlm.analyze, [frame_path], prompt)
    except Exception as e:
        logger.error("[static.vlm] camera=%s analyze error: %s", camera_id, e)
        return

    if result.get("result") == "normal":
        logger.debug("[static.vlm] normal: camera=%s", camera_id)
        return

    xadd(config.EVENTS_STREAM, {
        "camera_id": camera_id,
        "track": "static",
        "anomaly_type": result.get("anomaly_type", "normal"),
        "danger_level": result.get("danger_level", "none"),
        "description": result.get("description", ""),
        "timestamp": str(time.time()),
        "frame_path": frame_path,
    })
    logger.info("[static.vlm] event published: camera=%s type=%s",
                camera_id, result.get("anomaly_type"))


async def run_once(vlm: VLMClient, prompt: str) -> None:
    """모든 활성 카메라에 대해 동시 VLM 호출."""
    cameras = list_active_cameras()
    if not cameras:
        logger.debug("[static.vlm] no active cameras")
        return
    logger.info("[static.vlm] scanning %d cameras", len(cameras))
    await asyncio.gather(*[analyze_camera(vlm, prompt, c) for c in cameras])
