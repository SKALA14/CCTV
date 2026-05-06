# Redis Streams events 채널 구독 → PostgreSQL INSERT 백그라운드 워커.
# Consumer Group 방식으로 수신하며, main.py의 lifespan에서 asyncio 태스크로 실행된다.
"""
Redis 스트림 구독 워커.

alerts(emergency), events(general) 두 스트림을 asyncio.gather로 동시에 구독하며,
메시지가 도착하면 OpenAI 임베딩을 생성해 PostgreSQL event_logs 테이블에 저장한다.
진입점: run_worker() — main.py lifespan에서 asyncio.create_task로 실행된다.
"""

import asyncio
import logging
import uuid
from datetime import datetime, timezone

import redis.asyncio as aioredis
from openai import AsyncOpenAI
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.config import config
from app.db.session import AsyncSessionLocal
from app.db.models import CctvChannel, EventLog

logger = logging.getLogger(__name__)

CONSUMER_GROUP = "backend"
CONSUMER_NAME  = "backend-worker"

_redis_client: aioredis.Redis | None = None


def _get_client() -> aioredis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.from_url(config.REDIS_URL, decode_responses=True)
    return _redis_client


async def _ensure_consumer_groups() -> None:
    for stream in (config.ALERTS_STREAM, config.EVENTS_STREAM):
        try:
            await _get_client().xgroup_create(stream, CONSUMER_GROUP, id="0", mkstream=True)
        except aioredis.ResponseError:
            pass  # 이미 존재하는 그룹


# description 텍스트를 OpenAI Embeddings API로 VECTOR(1536)으로 변환한다.
async def _generate_embedding(client: AsyncOpenAI, text: str) -> list[float] | None:
    if not text:
        return None
    try:
        response = await client.embeddings.create(
            model="text-embedding-3-small",
            input=text,
        )
        return response.data[0].embedding
    except Exception as e:
        logger.warning("임베딩 생성 실패: %s", e)
        return None


# camera_id가 cctv_channels 테이블에 없으면 자동으로 INSERT한다. (FK 제약 충족용)
async def _ensure_channel(session, camera_id: str) -> None:
    exists = await session.scalar(
        select(CctvChannel).where(CctvChannel.camera_id == camera_id)
    )
    if not exists:
        stmt = insert(CctvChannel).values(
            camera_id=camera_id,
            camera_name=camera_id,
            source_type="unknown",
            source_url="",
        ).on_conflict_do_nothing()
        await session.execute(stmt)


# Redis 메시지의 timestamp 문자열을 datetime으로 변환한다. Unix 타임스탬프와 ISO 형식 모두 처리한다.
async def _parse_occurred_at(timestamp_str: str) -> datetime:
    try:
        ts = float(timestamp_str)
        return datetime.fromtimestamp(ts, tz=timezone.utc)
    except (ValueError, TypeError):
        pass
    try:
        return datetime.fromisoformat(timestamp_str).replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return datetime.now(tz=timezone.utc)


# Redis 메시지 하나를 파싱해서 임베딩을 생성하고 event_logs에 INSERT한다.
async def _process_message(
    fields: dict,
    pipeline: str,
    openai_client: AsyncOpenAI,
) -> None:
    camera_id    = fields.get("camera_id", "unknown")
    event_type   = fields.get("anomaly_type", "normal")
    danger_level = fields.get("danger_level", "none")
    description  = fields.get("description", "")
    source_path  = fields.get("source_path")
    occurred_at  = await _parse_occurred_at(fields.get("timestamp", ""))
    embedding    = await _generate_embedding(openai_client, description)

    async with AsyncSessionLocal() as session:
        async with session.begin():
            await _ensure_channel(session, camera_id)

            session.add(EventLog(
                event_id=uuid.uuid4(),
                camera_id=camera_id,
                pipeline=pipeline,
                event_type=event_type,
                danger_level=danger_level,
                description=description,
                source_path=source_path,
                occurred_at=occurred_at,
                embedding=embedding,
            ))

    logger.info("saved: pipeline=%s camera=%s event_type=%s", pipeline, camera_id, event_type)


# 지정한 Redis 스트림을 무한 루프로 구독하며 메시지가 올 때마다 _process_message를 호출한다.
async def _consume_stream(
    stream: str,
    pipeline: str,
    openai_client: AsyncOpenAI,
) -> None:
    r = _get_client()
    while True:
        try:
            results = await r.xreadgroup(
                CONSUMER_GROUP, CONSUMER_NAME,
                {stream: ">"},
                count=10,
                block=1000,
            )
            if not results:
                continue

            _, messages = results[0]
            for msg_id, fields in messages:
                try:
                    await _process_message(fields, pipeline, openai_client)
                    await r.xack(stream, CONSUMER_GROUP, msg_id)
                except Exception as e:
                    logger.error("메시지 처리 실패 msg_id=%s: %s", msg_id, e)

        except Exception as e:
            logger.error("스트림 읽기 오류 stream=%s: %s", stream, e)
            await asyncio.sleep(3)


# 워커 진입점. Redis 연결 후 alerts/events 스트림을 asyncio.gather로 동시에 구독 시작한다.
async def run_worker() -> None:
    openai_client = AsyncOpenAI()

    await _ensure_consumer_groups()
    logger.info("backend worker started")

    await asyncio.gather(
        _consume_stream(config.ALERTS_STREAM, "emergency", openai_client),
        _consume_stream(config.EVENTS_STREAM, "general",   openai_client),
    )