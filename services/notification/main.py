# notification 서비스 진입점.
# alerts/events 스트림을 Consumer Group으로 소비해 Slack으로 알림을 전송한다.

import logging
import os
import time

import redis

from slack import send_emergency_alert, send_general_alert

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

REDIS_URL      = os.environ["REDIS_URL"]
WEBHOOK_URL    = os.environ.get("SLACK_WEBHOOK_URL", "")
ALERTS_STREAM  = os.environ.get("ALERTS_STREAM", "alerts")
EVENTS_STREAM  = os.environ.get("EVENTS_STREAM", "events")

CONSUMER_GROUP = "notification"
CONSUMER_NAME  = "notification-worker"


def _ensure_groups(r: redis.Redis) -> None:
    """alerts/events 스트림에 Consumer Group을 생성한다(이미 있으면 무시)."""
    for stream in (ALERTS_STREAM, EVENTS_STREAM):
        try:
            r.xgroup_create(stream, CONSUMER_GROUP, id="$", mkstream=True)
        except redis.ResponseError:
            pass  # 이미 존재


def _consume(r: redis.Redis) -> None:
    """alerts/events에서 메시지를 읽어 종류별로 Slack 전송하고 처리 완료 후 xack한다."""
    streams = {ALERTS_STREAM: ">", EVENTS_STREAM: ">"}
    results = r.xreadgroup(
        CONSUMER_GROUP, CONSUMER_NAME,
        streams,
        count=10,
        block=1000,
    )
    if not results:
        return

    for stream, messages in results:
        for msg_id, fields in messages:
            try:
                # alerts는 긴급(YOLO), events는 일반(VLM) 알림으로 분기 처리한다.
                if stream == ALERTS_STREAM:
                    send_emergency_alert(fields, WEBHOOK_URL)
                else:
                    send_general_alert(fields, WEBHOOK_URL)
                r.xack(stream, CONSUMER_GROUP, msg_id)
            except Exception:
                # 한 건 실패가 루프를 끊지 않도록 로깅만 하고 다음 메시지로 진행(xack 생략 → 재처리 대상).
                logger.exception("알림 전송 실패 stream=%s msg_id=%s", stream, msg_id)


def main() -> None:
    """Redis 연결·그룹 생성 후 소비 루프를 돈다(스트림 읽기 오류 시 3초 후 재시도)."""
    r = redis.from_url(REDIS_URL, decode_responses=True)
    _ensure_groups(r)
    logger.info("notification 워커 시작 (alerts=%s, events=%s)", ALERTS_STREAM, EVENTS_STREAM)

    while True:
        try:
            _consume(r)
        except Exception:
            logger.exception("스트림 읽기 오류, 3초 후 재시도")
            time.sleep(3)


if __name__ == "__main__":
    main()
