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
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import cv2
import redis.asyncio as aioredis
from openai import AsyncOpenAI
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert

from app.config import config
from app.db.session import AsyncSessionLocal
from app.db.models import CctvChannel, EventLog

FRAMES_BASE      = Path(os.getenv("FRAME_STORAGE_PATH", "/frames"))
CLIPS_DIR        = FRAMES_BASE / "clips"
THUMBS_DIR       = FRAMES_BASE / "thumbnails"
CLIP_PADDING_SEC = 10

logger = logging.getLogger(__name__)

CONSUMER_GROUP = "backend"
CONSUMER_NAME  = "backend-worker"

# (camera_id, event_type) → 마지막 저장 시각 (monotonic)
_dedup_last_saved: dict[tuple[str, str], float] = {}
DEDUP_COOLDOWN_SEC = 30.0

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


def _build_clip_sync(event_id: str, camera_id: str, event_ts: float) -> tuple[str, str] | None:
    CLIPS_DIR.mkdir(parents=True, exist_ok=True)
    THUMBS_DIR.mkdir(parents=True, exist_ok=True)
    cam_dir = FRAMES_BASE / camera_id
    if not cam_dir.exists():
        return None

    start_ts, end_ts = event_ts - CLIP_PADDING_SEC, event_ts + CLIP_PADDING_SEC
    frame_files = []
    for f in sorted(cam_dir.glob("*.jpg")):
        try:
            ts = float(f.name.split("-")[0])
            if start_ts <= ts <= end_ts:
                frame_files.append((ts, f))
        except ValueError:
            continue

    if len(frame_files) < 2:
        return None

    first = cv2.imread(str(frame_files[0][1]))
    if first is None:
        return None
    h, w = first.shape[:2]

    thumb_path = THUMBS_DIR / f"{event_id}.jpg"
    cv2.imwrite(str(thumb_path), first)

    duration = frame_files[-1][0] - frame_files[0][0]
    fps = max(1.0, min(len(frame_files) / duration if duration > 0 else 2.0, 30.0))

    clip_path = CLIPS_DIR / f"{event_id}.mp4"
    writer = cv2.VideoWriter(str(clip_path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
    if not writer.isOpened():
        logger.error("VideoWriter 열기 실패 (코덱 미지원 가능): %s", clip_path)
        return None

    for _, f in frame_files:
        frame = cv2.imread(str(f))
        if frame is not None:
            writer.write(frame)
    writer.release()
    return f"/clips/{event_id}.mp4", f"/thumbnails/{event_id}.jpg"


async def _generate_and_update_clip(event_id: uuid.UUID, camera_id: str, frame_path: str | None) -> None:
    if not frame_path:
        return
    try:
        event_ts = float(Path(frame_path).name.split("-")[0])
    except (ValueError, IndexError):
        logger.warning("frame_path 타임스탬프 파싱 실패: %s", frame_path)
        return
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None, _build_clip_sync, str(event_id), camera_id, event_ts
        )
        if result:
            clip_url, thumbnail_url = result
            async with AsyncSessionLocal() as session:
                async with session.begin():
                    await session.execute(
                        update(EventLog)
                        .where(EventLog.event_id == event_id)
                        .values(clip_url=clip_url, thumbnail_url=thumbnail_url)
                    )
            logger.info("클립 생성 완료: event_id=%s url=%s", event_id, clip_url)
    except Exception as e:
        logger.warning("클립 생성 실패 event_id=%s: %s", event_id, e)


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

    dedup_key = (camera_id, event_type)
    now_mono  = time.monotonic()
    if now_mono - _dedup_last_saved.get(dedup_key, 0) < DEDUP_COOLDOWN_SEC:
        logger.info("dedup skip: camera=%s event_type=%s", camera_id, event_type)
        return
    _dedup_last_saved[dedup_key] = now_mono

    danger_level = fields.get("danger_level", "none")
    description  = fields.get("description", "")
    frame_path   = fields.get("frame")
    confidence   = fields.get("confidence")
    source_model = fields.get("source_model")
    occurred_at  = await _parse_occurred_at(fields.get("timestamp", ""))
    embed_text   = " ".join(filter(None, [
        fields.get("anomaly_type") or fields.get("event_type", ""),
        fields.get("danger_level", ""),
        description,
    ])).strip()
    embedding    = await _generate_embedding(openai_client, embed_text)

    event_id = uuid.uuid4()

    async with AsyncSessionLocal() as session:
        async with session.begin():
            await _ensure_channel(session, camera_id)

            session.add(EventLog(
                event_id=event_id,
                camera_id=camera_id,
                pipeline=pipeline,
                event_type=event_type,
                danger_level=danger_level,
                description=description,
                frame_path=frame_path,
                confidence=float(confidence) if confidence else None,
                source_model=source_model,
                source_path=frame_path,
                occurred_at=occurred_at,
                embedding=embedding,
                clip_url=None,
            ))

    logger.info("saved: pipeline=%s camera=%s event_type=%s", pipeline, camera_id, event_type)

    task = asyncio.create_task(_generate_and_update_clip(event_id, camera_id, frame_path))
    task.add_done_callback(
        lambda t: logger.warning("클립 태스크 예외: %s", t.exception())
        if not t.cancelled() and t.exception() else None
    )


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