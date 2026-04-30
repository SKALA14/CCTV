"""camera_id -> target_event 매핑 유틸.

우선순위:
1) config.CAMERA_TARGET_EVENT_MAP(JSON 문자열)
2) 코드 기본 매핑
3) DEFAULT_TARGET_EVENT
"""

from __future__ import annotations

import json
import logging
from typing import Literal

from config import config
from redis_client import get_client

logger = logging.getLogger(__name__)

TargetEvent = Literal["ppe", "fall", "intrusion", "fire"]

DEFAULT_TARGET_EVENT: TargetEvent = "fall"

# 필요 시 코드 기본값으로 사용 (예: 로컬 개발)
CAMERA_TARGET_EVENT_DEFAULTS: dict[str, TargetEvent] = {
    "cam_01": "intrusion",
    "cam_02": "fire",
    "cam_03": "ppe",
    "cam_04": "fall",
}


def _parse_env_map(raw: str) -> dict[str, TargetEvent]:
    if not raw.strip():
        return {}

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("invalid CAMERA_TARGET_EVENT_MAP JSON; fallback to defaults")
        return {}

    parsed: dict[str, TargetEvent] = {}
    valid = {"ppe", "fall", "intrusion", "fire"}

    for camera_id, target_event in data.items():
        event = str(target_event).strip().lower()
        if event in valid:
            parsed[str(camera_id)] = event  # type: ignore[assignment]
        else:
            logger.warning("unsupported target_event for %s: %s", camera_id, target_event)

    return parsed


def resolve_target_event(camera_id: str) -> TargetEvent:
    raw = get_client().get("camera_target_event_map") or "{}"
    redis_map = _parse_env_map(raw)
    
    if camera_id in redis_map:
        return redis_map[camera_id]
    if camera_id in CAMERA_TARGET_EVENT_DEFAULTS:
        return CAMERA_TARGET_EVENT_DEFAULTS[camera_id]
    return DEFAULT_TARGET_EVENT
