import logging
from datetime import datetime, timedelta
from typing import Any

import requests

logger = logging.getLogger(__name__)

HIGH_SEVERITIES = {"high"}
EMERGENCY_DEDUPE_WINDOW = timedelta(minutes=15)
_emergency_last_sent_at: dict[tuple[str, str], datetime] = {}

def _parse_timestamp(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value

    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value)

    if isinstance(value, str) and value.strip():
        try:
            return datetime.fromisoformat(value.strip())
        except ValueError:
            logger.debug("failed to parse alert timestamp: %s", value)

    return datetime.now()


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

    emoji = "🚨" if severity in HIGH_SEVERITIES else "⚠️"
    fallback_text = f"{emoji} [{severity}] {camera_id} | {timestamp} | {event_type} | {reason}"

    payload = {
        "text": fallback_text,
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"{emoji} 이상 상황 감지 알림",
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


def build_emergency_payload(alert: dict[str, Any]) -> dict[str, Any]:
    camera_id = alert.get("camera_id", "unknown")
    timestamp = alert.get("timestamp", "")
    anomaly_type = alert.get("anomaly_type", "emergency")
    frame = alert.get("frame", "")
    detections = alert.get("detections", [])
    classes = ", ".join(sorted({str(det.get("class", "unknown")) for det in detections}))
    max_conf = max((float(det.get("conf", 0)) for det in detections), default=0)

    fallback_text = (
        f"🚨 [EMERGENCY] {camera_id} | {timestamp} | "
        f"{anomaly_type} | {classes or 'detection'}"
    )

    detection_lines = [
        f"- {det.get('class', 'unknown')} ({float(det.get('conf', 0)):.2f})"
        for det in detections[:10]
    ]
    detection_text = "\n".join(detection_lines) if detection_lines else "탐지 결과 없음"

    return {
        "text": fallback_text,
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "🚨 긴급 상황 감지 알림",
                },
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*카메라 ID:*\n{camera_id}"},
                    {"type": "mrkdwn", "text": f"*발생 시각:*\n{timestamp}"},
                    {"type": "mrkdwn", "text": f"*이상 유형:*\n{anomaly_type}"},
                    {"type": "mrkdwn", "text": f"*탐지 수:*\n{len(detections)}"},
                    {"type": "mrkdwn", "text": f"*최고 신뢰도:*\n{max_conf:.2f}"},
                    {"type": "mrkdwn", "text": f"*프레임:*\n{frame}"},
                ],
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*YOLO 탐지 결과:*\n{detection_text}",
                },
            },
            {"type": "divider"},
        ],
    }


def should_notify_emergency(alert: dict[str, Any]) -> bool:
    camera_id = str(alert.get("camera_id", "unknown"))
    anomaly_type = str(alert.get("anomaly_type", "emergency"))
    timestamp = _parse_timestamp(alert.get("timestamp"))
    dedupe_key = (camera_id, anomaly_type)

    last_sent_at = _emergency_last_sent_at.get(dedupe_key)
    if last_sent_at and timestamp - last_sent_at < EMERGENCY_DEDUPE_WINDOW:
        logger.info(
            "duplicate emergency alert skipped: camera_id=%s anomaly_type=%s last_sent_at=%s",
            camera_id,
            anomaly_type,
            last_sent_at,
        )
        return False

    return True


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
    if not should_notify_emergency(alert):
        return

    _post_to_slack(webhook_url, build_emergency_payload(alert))
    camera_id = str(alert.get("camera_id", "unknown"))
    anomaly_type = str(alert.get("anomaly_type", "emergency"))
    _emergency_last_sent_at[(camera_id, anomaly_type)] = _parse_timestamp(
        alert.get("timestamp")
    )


def send_general_alert(vlm_result: dict[str, Any], webhook_url: str) -> None:
    if not should_notify_general(vlm_result):
        logger.info("general alert condition not met; skip Slack notification")
        return

    _post_to_slack(webhook_url, build_general_payload(vlm_result))
