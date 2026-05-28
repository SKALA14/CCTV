# services/inference/cleaner/process.py
"""TTL 기반 프레임 JPEG 정리 프로세스."""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path

from config import config

logger = logging.getLogger(__name__)


SKIP_DIRS = {"snapshots"}


def _scan_and_delete() -> int:
    """frames 디렉토리의 카메라별 jpg만 TTL 기반 삭제. snapshots는 제외."""
    base = Path(config.FRAME_STORAGE_PATH)
    if not base.exists():
        return 0
    now = time.time()
    deleted = 0

    for cam_dir in os.scandir(base):
        if not cam_dir.is_dir() or cam_dir.name in SKIP_DIRS:
            continue
        for entry in os.scandir(cam_dir.path):
            if not entry.is_file() or not entry.name.lower().endswith((".jpg", ".jpeg")):
                continue
            try:
                if now - entry.stat().st_mtime < config.CLEANER_TTL_SEC:
                    continue
                os.remove(entry.path)
                deleted += 1
            except OSError as e:
                logger.error("[cleaner] failed to delete %s: %s", entry.path, e)
    return deleted


def run() -> None:
    """Cleaner 진입점. CLEANER_INTERVAL_SEC마다 TTL 스캔 실행."""
    logging.basicConfig(level=logging.INFO, format="%(processName)s [%(levelname)s] %(message)s")
    logger.info("[cleaner] started (interval=%ss, ttl=%ss)",
                config.CLEANER_INTERVAL_SEC, config.CLEANER_TTL_SEC)

    while True:
        try:
            deleted = _scan_and_delete()
            if deleted:
                logger.info("[cleaner] deleted %d files", deleted)
        except Exception as e:
            logger.error("[cleaner] scan error: %s", e)
        time.sleep(config.CLEANER_INTERVAL_SEC)
