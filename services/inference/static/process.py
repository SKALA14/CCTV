# services/inference/static/process.py
"""Static 프로세스 진입점. 시작 직후 1회 + STATIC_INTERVAL_SEC 주기 반복."""

from __future__ import annotations

import asyncio
import logging

from config import config
from static import vlm_worker
from vlm.client import VLMClient

logger = logging.getLogger(__name__)


async def _scheduler() -> None:
    vlm = VLMClient()
    logger.info("[static] scheduler started (interval=%ss)", config.STATIC_INTERVAL_SEC)

    while True:
        try:
            await vlm_worker.run_once(vlm, config.STATIC_PROMPT_FILE)
        except Exception as e:
            logger.error("[static] scan error: %s", e)
        await asyncio.sleep(config.STATIC_INTERVAL_SEC)


def run() -> None:
    """Static 진입점."""
    logging.basicConfig(level=logging.INFO, format="%(processName)s [%(levelname)s] %(message)s")
    asyncio.run(_scheduler())
