# Redis 연결과 Streams 유틸 함수를 정의한다.
# 정의: get_client·ensure_group·xreadgroup·xadd·xack·mark_processed.
# 입력: config.REDIS_URL (연결), stream/group/consumer 문자열 (각 함수 인자).
# 출력: 메시지 리스트(xreadgroup), msg_id(xadd), ACK 카운트(xack), 삭제 대상 여부 bool(mark_processed).

import redis as _redis
from config import config

_client: _redis.Redis | None = None


def get_client() -> _redis.Redis: # 
    global _client
    if _client is None:
        _client = _redis.from_url(config.REDIS_URL, decode_responses=True)
    return _client


def ensure_group(stream: str, group: str) -> None:
    try:
        get_client().xgroup_create(stream, group, id="0", mkstream=True)
    except _redis.exceptions.ResponseError:
        pass  # 이미 존재하는 그룹


def xreadgroup(
    stream: str,
    group: str,
    consumer: str,
    count: int = 1,
    block_ms: int = 1000,
) -> list[tuple[str, dict]]:
    result = get_client().xreadgroup(
        group, consumer, {stream: ">"}, count=count, block=block_ms
    )
    if not result:
        return []
    _, messages = result[0]
    return messages  # [(msg_id, {field: value, ...}), ...]


def xadd(stream: str, fields: dict) -> str:
    return get_client().xadd(stream, fields)


def xack(stream: str, group: str, *msg_ids: str) -> int:
    return get_client().xack(stream, group, *msg_ids)


def mark_processed(frame_path: str, total: int = 2) -> bool:
    """두 파이프라인이 모두 ACK 하면 True 반환 → 파일 삭제 대상."""
    r = get_client()
    key = f"ack_count:{frame_path}"
    count = r.incr(key)
    if count == 1:
        r.expire(key, 3600)
    if count >= total:
        r.delete(key)
        r.rpush("delete_queue", frame_path)
        return True
    return False
