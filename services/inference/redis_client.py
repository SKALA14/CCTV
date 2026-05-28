# services/inference/redis_client.py
"""Redis 연결 및 Streams 헬퍼."""

from __future__ import annotations

import redis as _redis

from config import config


_client: _redis.Redis | None = None


def get_client() -> _redis.Redis:
    """프로세스별로 lazy-initialized Redis 클라이언트 반환."""
    global _client
    if _client is None:
        _client = _redis.from_url(config.REDIS_URL, decode_responses=True)
    return _client


def ensure_group(stream: str, group: str) -> None:
    """Consumer Group이 없으면 생성, 있으면 무시."""
    try:
        get_client().xgroup_create(stream, group, id="$", mkstream=True)
    except _redis.exceptions.ResponseError:
        pass


def init_consumer_groups() -> None:
    """frames 스트림에 emergency / dynamic 두 Consumer Group을 선언한다."""
    ensure_group(config.FRAMES_STREAM, config.EMERGENCY_GROUP)
    ensure_group(config.FRAMES_STREAM, config.DYNAMIC_GROUP)


def xreadgroup(
    stream: str,
    group: str,
    consumer: str,
    count: int = 1,
    block_ms: int = 1000,
) -> list[tuple[str, dict]]:
    """단일 stream에서 메시지를 읽는다. block 동안 대기."""
    result = get_client().xreadgroup(
        group, consumer, {stream: ">"}, count=count, block=block_ms
    )
    if not result:
        return []
    _, messages = result[0]
    return messages


def xadd(stream: str, fields: dict, maxlen: int | None = None) -> str:
    if maxlen:
        return get_client().xadd(stream, fields, maxlen=maxlen, approximate=True)
    return get_client().xadd(stream, fields)


def xack(stream: str, group: str, *msg_ids: str) -> int:
    return get_client().xack(stream, group, *msg_ids)
