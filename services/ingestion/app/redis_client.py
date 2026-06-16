# Redis 클라이언트 싱글톤. 연결을 1회 맺어 재사용하고, 실패 시 3초 간격으로 최대 5회 재시도한다.

import time
import logging

import redis

from .config import config

logger = logging.getLogger(__name__)

_redis_client = None  # 최초 연결 후 캐싱하는 모듈 수준 싱글톤


def get_client() -> redis.Redis:
    """Redis 클라이언트를 반환한다(최초 1회만 연결, 이후 캐시된 인스턴스 재사용)."""
    global _redis_client
    if _redis_client is not None:
        return _redis_client

    for attempt in range(1, 6):
        try:
            client = redis.from_url(config.REDIS_URL, decode_responses=True)
            client.ping()
            _redis_client = client
            logger.info("Redis 연결 성공: %s", config.REDIS_URL)
            return _redis_client
        except redis.exceptions.ConnectionError:
            logger.warning("Redis 연결 실패 (%d/5), 3초 후 재시도", attempt)
            time.sleep(3)

    raise RuntimeError("Redis에 연결할 수 없습니다")
