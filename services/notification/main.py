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
    for stream in (ALERTS_STREAM, EVENTS_STREAM):
        try:
            r.xgroup_create(stream, CONSUMER_GROUP, id="$", mkstream=True)
        except redis.ResponseError:
            pass  # 이미 존재


def _consume(r: redis.Redis) -> None:
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
                if stream == ALERTS_STREAM:
                    send_emergency_alert(fields, WEBHOOK_URL)
                else:
                    send_general_alert(fields, WEBHOOK_URL)
                r.xack(stream, CONSUMER_GROUP, msg_id)
            except Exception:
                logger.exception("알림 전송 실패 stream=%s msg_id=%s", stream, msg_id)


def main() -> None:
    r = redis.from_url(REDIS_URL, decode_responses=True)
    _ensure_groups(r)
    logger.info("notification worker started (alerts=%s, events=%s)", ALERTS_STREAM, EVENTS_STREAM)

    while True:
        try:
            _consume(r)
        except Exception:
            logger.exception("스트림 읽기 오류, 3초 후 재시도")
            time.sleep(3)


if __name__ == "__main__":
    main()
