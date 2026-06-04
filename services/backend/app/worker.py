# Redis Streams events 채널 구독 → PostgreSQL INSERT 백그라운드 워커.
# Consumer Group 방식으로 수신하며, main.py의 lifespan에서 asyncio 태스크로 실행된다.
"""
Redis 스트림 구독 워커.

events(VLM 결과) 스트림만 구독해 임베딩을 생성하고 PostgreSQL event_logs 테이블에 저장한다.
alerts(YOLO)는 notification과 ws.py가 자체적으로 처리하므로 backend는 보지 않는다.
진입점: run_worker() — main.py lifespan에서 asyncio.create_task로 실행된다.
"""

import asyncio
import logging
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import shutil
import redis.asyncio as aioredis
from openai import AsyncOpenAI
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert

from app.api.embed_describer import describe_for_embedding as _describe_embed
from app.config import config
from app.db.session import AsyncSessionLocal
from app.db.models import CctvChannel, EventLog

FRAMES_BASE     = Path(os.getenv("FRAME_STORAGE_PATH", "/frames"))
SNAPSHOTS_DIR   = FRAMES_BASE / "snapshots"
SNAPSHOT_WINDOW_SEC = 5.0
SNAPSHOT_COUNT  = 5

logger = logging.getLogger(__name__)

CONSUMER_GROUP = "backend"
CONSUMER_NAME  = "backend-worker"

# 같은 (camera_id, event_type)이 INCIDENT_GAP_SEC 안에 또 들어오면 snapshot 생성 skip.
# 대표(=incident 첫 이벤트)에만 snapshot이 남고, 후속은 snapshot_urls=NULL로 적재됨.
_snapshot_last: dict[tuple[str, str], float] = {}

_redis_client: aioredis.Redis | None = None


def _get_client() -> aioredis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.from_url(config.REDIS_URL, decode_responses=True)
    return _redis_client


async def _ensure_consumer_groups() -> None:
    # DB 적재는 VLM(events) 결과만 수행. YOLO(alerts)는 notification/ws가 자체적으로 처리.
    try:
        await _get_client().xgroup_create(config.EVENTS_STREAM, CONSUMER_GROUP, id="0", mkstream=True)
    except aioredis.ResponseError:
        pass


def _save_snapshots_sync(event_id: str, camera_id: str, frame_path: str) -> list[str]:
    """이벤트 ±SNAPSHOT_WINDOW_SEC에서 SNAPSHOT_COUNT장 균등 선별해 저장."""
    cam_dir = FRAMES_BASE / camera_id
    if not cam_dir.exists():
        logger.warning("snapshot: camera dir 없음 %s", cam_dir)
        return []
    try:
        event_ts = float(Path(frame_path).name.split("-")[0])
    except (ValueError, IndexError):
        logger.warning("snapshot: frame_path timestamp 파싱 실패 %s", frame_path)
        return []

    start_ts, end_ts = event_ts - SNAPSHOT_WINDOW_SEC, event_ts + SNAPSHOT_WINDOW_SEC
    candidates = []
    for f in sorted(cam_dir.glob("*.jpg")):
        try:
            ts = float(f.name.split("-")[0])
            if start_ts <= ts <= end_ts:
                candidates.append(f)
        except ValueError:
            continue

    if not candidates:
        return []

    n = min(SNAPSHOT_COUNT, len(candidates))
    if n == 1:
        selected = [candidates[0]]
    else:
        step = (len(candidates) - 1) / (n - 1)
        selected = [candidates[round(i * step)] for i in range(n)]

    event_dir = SNAPSHOTS_DIR / event_id
    event_dir.mkdir(parents=True, exist_ok=True)
    urls: list[str] = []
    for i, src in enumerate(selected, 1):
        dst = event_dir / f"{i:02d}.jpg"
        try:
            shutil.copy2(src, dst)
            urls.append(f"/snapshots/{event_id}/{i:02d}.jpg")
        except OSError as e:
            logger.warning("snapshot 복사 실패 %s → %s: %s", src, dst, e)
    return urls


async def _save_snapshots(event_id: uuid.UUID, camera_id: str, frame_path: str | None) -> None:
    if not frame_path:
        return
    try:
        loop = asyncio.get_event_loop()
        urls = await loop.run_in_executor(
            None, _save_snapshots_sync, str(event_id), camera_id, frame_path
        )
        if urls:
            async with AsyncSessionLocal() as session:
                async with session.begin():
                    await session.execute(
                        update(EventLog)
                        .where(EventLog.event_id == event_id)
                        .values(snapshot_urls=urls, thumbnail_url=urls[0])
                    )
            logger.info("snapshots 저장 완료: event_id=%s count=%d", event_id, len(urls))
    except Exception as e:
        logger.warning("snapshots 저장 실패 event_id=%s: %s", event_id, e)


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
    frame_path   = fields.get("frame_path")
    confidence   = fields.get("confidence")
    source_model = fields.get("source_model")
    track        = fields.get("track")
    occurred_at  = await _parse_occurred_at(fields.get("timestamp", ""))
    embed_text   = await _describe_embed(
        event_type=fields.get("anomaly_type") or fields.get("event_type", ""),
        danger_level=fields.get("danger_level", ""),
        description=description,
    )
    embedding    = await _generate_embedding(openai_client, embed_text)

    event_id = uuid.uuid4()

    async with AsyncSessionLocal() as session:
        async with session.begin():
            await _ensure_channel(session, camera_id)
            camera_name = await session.scalar(
                select(CctvChannel.camera_name).where(CctvChannel.camera_id == camera_id)
            )

            session.add(EventLog(
                event_id=event_id,
                camera_id=camera_id,
                camera_name=camera_name,
                pipeline=track or pipeline,
                event_type=event_type,
                danger_level=danger_level,
                description=description,
                frame_path=frame_path,
                confidence=float(confidence) if confidence else None,
                source_model=source_model,
                source_path=frame_path,
                occurred_at=occurred_at,
                embedding=embedding,
            ))

    logger.info("saved: pipeline=%s camera=%s event_type=%s", pipeline, camera_id, event_type)

    # incident 첫 이벤트(=GAP 밖)에만 snapshot 생성. 후속은 skip해서 디스크 절약.
    dedup_key = (camera_id, event_type)
    now_mono  = time.monotonic()
    if now_mono - _snapshot_last.get(dedup_key, 0) >= config.INCIDENT_GAP_SEC:
        _snapshot_last[dedup_key] = now_mono
        task = asyncio.create_task(_save_snapshots(event_id, camera_id, frame_path))
        task.add_done_callback(
            lambda t: logger.warning("snapshots 태스크 예외: %s", t.exception())
            if not t.cancelled() and t.exception() else None
        )
    else:
        logger.debug("snapshot skip (incident 후속): camera=%s event_type=%s", camera_id, event_type)


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


# 워커 진입점. events 스트림(VLM 결과)만 구독해 DB에 적재한다.
# alerts(YOLO)는 notification과 ws.py가 자체적으로 처리하므로 backend는 보지 않는다.
async def run_worker() -> None:
    openai_client = AsyncOpenAI()

    await _ensure_consumer_groups()
    logger.info("backend worker started (events stream only)")

    await _consume_stream(config.EVENTS_STREAM, "general", openai_client)
