import time
import logging

import redis

from .config import config

logger = logging.getLogger(__name__)

_redis_client = None


def get_client() -> redis.Redis:
    global _redis_client
    if _redis_client is not None:
        return _redis_client

    for attempt in range(1, 6):
        try:
            client = redis.from_url(config.REDIS_URL, decode_responses=True)
            client.ping()
            _redis_client = client
            return _redis_client
        except redis.exceptions.ConnectionError:
            logger.warning("Redis 연결 실패 (%d/5), 3초 후 재시도", attempt)
            time.sleep(3)

    raise RuntimeError("Redis에 연결할 수 없습니다")
