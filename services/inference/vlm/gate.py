"""VLM 이벤트 발행 전 Quality Gate.

Confidence Gate: 저확신 anomaly 억제
Cross-pipeline Dedup: 동일 카메라 중복 이벤트 억제
"""

from __future__ import annotations

import logging

from config import config
from redis_client import get_client

logger = logging.getLogger(__name__)


def should_publish(result: dict, camera_id: str, pipeline: str) -> bool:
    """Confidence Gate + Dedup Check 순차 적용.

    True면 이벤트 발행 허용, False면 억제.
    normal 결과는 Gate 없이 True 반환 (기존 동작 유지).
    """
    if result.get("result") != "anomaly":
        return True

    # --- Confidence Gate ---
    confidence = float(result.get("confidence", 0.0))
    threshold = config.MIN_CONFIDENCE
    # Future: camera:{camera_id}:min_confidence Redis key로 카메라별 오버라이드
    # Future: danger_level별 차등 임계값

    if confidence < threshold:
        logger.info(
            "[%s] SUPPRESSED cam=%s confidence=%.2f threshold=%.2f danger=%s type=%s",
            pipeline, camera_id, confidence, threshold,
            result.get("danger_level", "none"),
            result.get("anomaly_type", "GENERAL"),
        )
        return False

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
