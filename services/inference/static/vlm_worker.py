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
from vlm.client import VLMClient, render_prompt
from vlm.gate import should_publish, mark_published

logger = logging.getLogger(__name__)


def list_active_cameras() -> list[tuple[str, str]]:
    """Redis camera:{site_id}:{cam_id}:source_url 키에서 (site_id, cam_id) 목록 반환.

    신포맷 키는 ':' 기준 4-part: ["camera", "{site_id}", "{cam_id}", "source_url"]
    """
    cameras: list[tuple[str, str]] = []
    for key in get_client().scan_iter(match="camera:*:source_url"):
        parts = key.split(":")
        if len(parts) == 4:  # camera:{site_id}:{cam_id}:source_url
            cameras.append((parts[1], parts[2]))
    return sorted(cameras)


def latest_frame_path(camera_id: str) -> str | None:
    """카메라 디렉토리에서 가장 최근에 수정된 JPEG 경로 반환.

    camera_id는 순수 cam_id("cam1" 등) — site_id 포함하지 않음.
    프레임은 /frames/{cam_id}/ 에 저장됨.
    """
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


async def analyze_camera(
    vlm: VLMClient,
    prompt_file: str,
    site_id: str,
    camera_id: str,
) -> None:
    """단일 카메라에 대한 static VLM 호출. 이상 응답이면 events 스트림에 발행.

    site_id: 현장 UUID 문자열 (gate/xadd에 사용)
    camera_id: 순수 cam_id ("cam1" 등, 프레임 경로용)
    """
    frame_path = latest_frame_path(camera_id)
    if frame_path is None:
        return

    # compound key를 render_prompt에 넘기면 내부 Redis 조회가 올바른 포맷을 사용
    # camera_instruction:{site_id}:{cam_id} / camera:{site_id}:{cam_id}:zone
    full_cam_id = f"{site_id}:{camera_id}" if site_id else camera_id
    prompt, categories = render_prompt(prompt_file, full_cam_id)

    logger.info("[static.vlm] → VLM 호출: site=%s camera=%s", site_id, camera_id)
    t0 = time.monotonic()
    loop = asyncio.get_running_loop()
    try:
        result = await loop.run_in_executor(None, vlm.analyze, [frame_path], prompt, categories)
    except Exception as e:
        logger.error("[static.vlm] camera=%s analyze error: %s", camera_id, e)
        return
    elapsed = time.monotonic() - t0

    if result.get("result") != "anomaly":
        logger.info("[static.vlm] ← %s (%.1fs): camera=%s", result.get("result"), elapsed, camera_id)
        return

    if not should_publish(result, full_cam_id, "static"):
        return

    xadd(config.EVENTS_STREAM, {
        "camera_id":   camera_id,
        "site_id":     site_id,
        "track":       "static",
        "anomaly_type":  result.get("anomaly_type", "normal"),
        "danger_level":  result.get("danger_level", "none"),
        "description":   result.get("description", ""),
        "timestamp":     str(time.time()),
        "frame_path":    frame_path,
    }, maxlen=config.EVENTS_MAXLEN)
    mark_published(full_cam_id, "static")
    logger.info("[static.vlm] ← anomaly (%.1fs): site=%s camera=%s type=%s",
                elapsed, site_id, camera_id, result.get("anomaly_type"))


async def run_once(vlm: VLMClient, prompt_file: str) -> None:
    """모든 활성 카메라에 대해 동시 VLM 호출."""
    cameras = list_active_cameras()
    if not cameras:
        logger.debug("[static.vlm] no active cameras")
        return
    logger.info("[static.vlm] scanning %d cameras", len(cameras))
    await asyncio.gather(*[
        analyze_camera(vlm, prompt_file, sid, cid)
        for sid, cid in cameras
    ])
