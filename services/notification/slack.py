import logging
import os
import time
from datetime import datetime, timezone, timedelta
from typing import Any

_KST = timezone(timedelta(hours=9))

import requests

logger = logging.getLogger(__name__)

HIGH_SEVERITIES = {"critical", "high"}

INCIDENT_GAP_SEC: float = float(os.environ.get("INCIDENT_GAP_SEC", "10"))
_last_sent: dict[tuple[str, str], float] = {}


def should_notify_general(vlm_result: dict[str, Any]) -> bool:
    if not vlm_result.get("is_anomaly", False):
        return False

    severity = str(vlm_result.get("danger_level", "")).lower()
    if not severity:
        return True
    return severity in HIGH_SEVERITIES


def build_general_payload(vlm_result: dict[str, Any]) -> dict[str, Any]:
    severity = str(vlm_result.get("danger_level", "")).lower()
    camera_id = vlm_result.get("camera_id", "unknown")
    timestamp = vlm_result.get("timestamp", "")
    event_type = vlm_result.get("event_type", "general")
    score = vlm_result.get("score", "")
    reason = vlm_result.get("reason") or vlm_result.get("description", "")
    rule = vlm_result.get("rule", "")
    frame = vlm_result.get("frame", "")

    fallback_text = f"[{severity}] {camera_id} | {timestamp} | {event_type} | {reason}"

    payload = {
        "text": fallback_text,
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "이상 상황 감지 알림",
                },
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*카메라 ID:*\n{camera_id}"},
                    {"type": "mrkdwn", "text": f"*발생 시각:*\n{timestamp}"},
                    {"type": "mrkdwn", "text": f"*이벤트 유형:*\n{event_type}"},
                    {"type": "mrkdwn", "text": f"*위험도:*\n{severity}"},
                    {"type": "mrkdwn", "text": f"*점수:*\n{score}"},
                    {"type": "mrkdwn", "text": f"*프레임:*\n{frame}"},
                ],
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*판단 근거:*\n{reason}",
                },
            },
        ],
    }

    if rule:
        payload["blocks"].append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*적용 규칙 / 참고 기준:*\n{rule}",
                },
            }
        )

    payload["blocks"].append({"type": "divider"})
    return payload


_ANOMALY_TYPE_DISPLAY = {"fallen": "fall"}


def build_emergency_payload(alert: dict[str, Any]) -> dict[str, Any]:
    camera_id    = alert.get("camera_name") or alert.get("camera_id", "unknown")
    raw_ts       = alert.get("timestamp", "")
    try:
        timestamp = datetime.fromtimestamp(float(raw_ts), tz=_KST).strftime("%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError):
        timestamp = raw_ts
    raw_type     = alert.get("anomaly_type", "emergency")
    anomaly_type = _ANOMALY_TYPE_DISPLAY.get(raw_type, raw_type)
    description  = alert.get("description", "")

    fallback_text = f"[EMERGENCY] {camera_id} | {timestamp} | {anomaly_type}"

    return {
        "text": fallback_text,
        "blocks": [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": "🚨 긴급 상황 감지"},
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"*카메라 ID:* {camera_id}\n"
                        f"*발생 시각:* {timestamp}\n"
                        f"*이상 유형:* {anomaly_type}\n"
                        f"*설명:* {description}"
                    ),
                },
            },
            {"type": "divider"},
        ],
    }


def _normalize_event_type(event_type: str) -> str:
    return "fire" if event_type == "smoke" else event_type


def _dedup(camera_id: str, event_type: str) -> bool:
    """마지막 탐지로부터 INCIDENT_GAP_SEC 이상 끊기면 새 사건으로 판단."""
    key = (camera_id, _normalize_event_type(event_type))
    now = time.monotonic()
    last = _last_sent.get(key, 0.0)
    _last_sent[key] = now
    return now - last < INCIDENT_GAP_SEC


def _post_to_slack(webhook_url: str, payload: dict[str, Any]) -> None:
    if not webhook_url:
        logger.warning("SLACK_WEBHOOK_URL is not configured; skip Slack notification")
        return

    response = requests.post(webhook_url, json=payload, timeout=5)
    if response.status_code != 200 or response.text.strip() != "ok":
        raise RuntimeError(
            f"Slack 전송 실패: status={response.status_code}, body={response.text}"
        )


def send_emergency_alert(alert: dict[str, Any], webhook_url: str) -> None:
    camera_id    = str(alert.get("camera_id", "unknown"))
    anomaly_type = str(alert.get("anomaly_type", "emergency"))
    if _dedup(camera_id, anomaly_type):
        logger.info("emergency alert deduped (incident): camera=%s type=%s", camera_id, anomaly_type)
        return

    _post_to_slack(webhook_url, build_emergency_payload(alert))


def send_general_alert(vlm_result: dict[str, Any], webhook_url: str) -> None:
    if not should_notify_general(vlm_result):
        logger.info("general alert condition not met; skip Slack notification")
        return

    camera_id  = str(vlm_result.get("camera_id", "unknown"))
    event_type = str(vlm_result.get("anomaly_type") or vlm_result.get("event_type", "general"))
    if _dedup(camera_id, event_type):
        logger.info("general alert deduped (incident): camera=%s type=%s", camera_id, event_type)
        return

    _post_to_slack(webhook_url, build_general_payload(vlm_result))
