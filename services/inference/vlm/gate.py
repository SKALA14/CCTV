"""VLM 이벤트 발행 전 Quality Gate.

Cross-pipeline Dedup: 동일 카메라 중복 이벤트 억제
"""

from __future__ import annotations

import logging

from config import config
from redis_client import get_client

logger = logging.getLogger(__name__)


def should_publish(result: dict, camera_id: str, pipeline: str) -> bool:
    """Dedup Check 적용.

    True면 이벤트 발행 허용, False면 억제.
    """
    if result.get("result") != "anomaly":
        return True

    # --- Cross-pipeline Dedup ---
    dedup_key = f"event:dedup:{camera_id}"
    try:
        client = get_client()
        existing = client.get(dedup_key)
    except Exception as e:
        logger.warning("[%s] dedup check 실패 cam=%s: %s (발행 허용)", pipeline, camera_id, e)
        return True

    if existing:
        try:
            ttl = client.ttl(dedup_key)
        except Exception:
            ttl = -1
        logger.info(
            "[%s] DEDUP_HIT cam=%s already_fired_by=%s ttl_remaining=%ds",
            pipeline, camera_id, existing, ttl,
        )
        return False

    # Future: danger_level == "critical" → dedup bypass
    # Future: violated_index가 다르면 dedup 면제

    return True


def mark_published(camera_id: str, pipeline: str) -> None:
    """이벤트 발행 성공 후 dedup 키 설정."""
    dedup_key = f"event:dedup:{camera_id}"
    try:
        get_client().setex(dedup_key, config.DEDUP_TTL_SEC, pipeline)
    except Exception as e:
        logger.warning("[%s] dedup 키 설정 실패 cam=%s: %s", pipeline, camera_id, e)
