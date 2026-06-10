# services/inference/static/process.py
"""Static 프로세스 진입점. 시작 직후 1회 + STATIC_INTERVAL_SEC 주기 반복.
채널 등록 이벤트(camera:registered) 수신 시 해당 카메라 즉시 스캔.
"""

from __future__ import annotations

import asyncio
import logging

from config import config
from redis_client import get_async_client
from static import vlm_worker
from vlm.client import VLMClient

logger = logging.getLogger(__name__)


async def _scheduler(vlm: VLMClient) -> None:
    logger.info("[static] scheduler started (interval=%ss)", config.STATIC_INTERVAL_SEC)
    while True:
        try:
            await vlm_worker.run_once(vlm, config.STATIC_PROMPT_FILE)
        except Exception as e:
            logger.error("[static] scan error: %s", e)
        await asyncio.sleep(config.STATIC_INTERVAL_SEC)


_FRAME_WAIT_INTERVAL = 2   # 프레임 대기 폴링 간격 (초)
_FRAME_WAIT_TIMEOUT  = 30  # 최대 대기 시간 (초)


async def _wait_for_fresh_frame(cam_id: str, registered_at: float) -> bool:
    """등록 시각 이후에 저장된 프레임이 생길 때까지 최대 _FRAME_WAIT_TIMEOUT초 대기.

    registered_at 이전의 구 영상 프레임은 무시한다.
    이전 영상의 스테일 프레임으로 VLM이 오호출되는 버그를 방지한다.
    """
    from pathlib import Path
    cam_dir = Path(config.FRAME_STORAGE_PATH) / cam_id
    for _ in range(_FRAME_WAIT_TIMEOUT // _FRAME_WAIT_INTERVAL):
        if cam_dir.exists() and any(
            f.suffix.lower() in (".jpg", ".jpeg") and f.stat().st_mtime >= registered_at
            for f in cam_dir.iterdir()
            if f.is_file()
        ):
            return True
        await asyncio.sleep(_FRAME_WAIT_INTERVAL)
    return False


async def _scan_after_registration(vlm: VLMClient, site_id: str, cam_id: str) -> None:
    """카메라 등록 후 새 프레임 대기 → 즉시 스캔 (독립 태스크로 실행).

    site_id: 현장 UUID 문자열
    cam_id:  순수 camera id ("cam1" 등) — 프레임 경로 탐색용
    """
    import time
    registered_at = time.time()
    try:
        if not await _wait_for_fresh_frame(cam_id, registered_at):
            logger.warning("[static] 새 프레임 대기 타임아웃 camera=%s (스캔 건너뜀)", cam_id)
            return
        logger.info("[static] 새 프레임 확인 → 즉시 스캔: site=%s camera=%s", site_id, cam_id)
        await vlm_worker.analyze_camera(vlm, config.STATIC_PROMPT_FILE, site_id, cam_id)
    except Exception as e:
        logger.error("[static] 즉시 스캔 실패 camera=%s: %s", cam_id, e)


async def _listen_registrations(vlm: VLMClient) -> None:
    """camera:registered 채널 구독 → 신규 카메라 즉시 스캔.

    메시지 포맷: "{site_id}:{cam_id}" (예: "abc12345-...:cam1")
    """
    pubsub = get_async_client().pubsub()
    await pubsub.subscribe("camera:registered")
    logger.info("[static] 채널 등록 이벤트 구독 시작")
    async for message in pubsub.listen():
        if message["type"] != "message":
            continue
        data = message["data"]  # "{site_id}:{cam_id}"
        # site_id는 UUID 형식 (하이픈 포함), cam_id는 "cam0"~"cam3"
        # "{site_id}:{cam_id}"에서 첫 번째 ':'을 기준으로 분리
        parts = data.split(":", 1)
        if len(parts) == 2:
            site_id, cam_id = parts
        else:
            site_id, cam_id = "", data
        logger.info("[static] 신규 카메라 등록 감지: site=%s cam=%s → 비동기 스캔 예약",
                    site_id, cam_id)
        asyncio.create_task(_scan_after_registration(vlm, site_id, cam_id))


async def _main() -> None:
    vlm = VLMClient()
    await asyncio.gather(
        _scheduler(vlm),
        _listen_registrations(vlm),
    )


def run() -> None:
    """Static 진입점."""
    logging.basicConfig(level=logging.INFO, format="%(processName)s [%(levelname)s] %(message)s")
    asyncio.run(_main())
