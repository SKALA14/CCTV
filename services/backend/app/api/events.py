import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from openai import AsyncOpenAI
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.db.models import EventLog, CctvChannel
from app.api.schemas import EventLogRead, EventListResponse
from app.api.time_parser import parse_time_expression

router = APIRouter()
_openai = AsyncOpenAI()


def _to_schema(event: EventLog, channel_name: str | None = None, similarity: float | None = None) -> EventLogRead:
    return EventLogRead(
        id=event.event_id,
        channel_id=event.camera_id,
        channel_name=channel_name or event.camera_id,
        pipeline=event.pipeline,
        event_type=event.event_type,
        danger_level=event.danger_level,
        reason=event.description,
        confidence=event.confidence,
        vlm_confidence=None,
        pose_event=None,
        source_model=event.source_model,
        frame_path=event.frame_path,
        thumbnail_url=event.thumbnail_url,
        clip_url=event.clip_url,
        source_path=event.source_path,
        occurred_at=event.occurred_at,
        created_at=event.created_at,
        similarity=similarity,
    )


async def _fetch_channel_names(db: AsyncSession, camera_ids: list[str]) -> dict[str, str]:
    result = await db.execute(
        select(CctvChannel).where(CctvChannel.camera_id.in_(camera_ids))
    )
    return {ch.camera_id: ch.camera_name for ch in result.scalars().all()}


@router.get("/events", response_model=EventListResponse)
async def list_events(
    channel_id:   Optional[str] = Query(None),
    pipeline:     Optional[str] = Query(None),
    event_type:   Optional[str] = Query(None),
    danger_level: Optional[str] = Query(None),
    skip:  int = Query(0,  ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    query = select(EventLog)

    if channel_id:
        query = query.where(EventLog.camera_id == channel_id)
    if pipeline:
        query = query.where(EventLog.pipeline == pipeline)
    if event_type:
        query = query.where(EventLog.event_type == event_type)
    if danger_level:
        query = query.where(EventLog.danger_level == danger_level)

    total = await db.scalar(select(func.count()).select_from(query.subquery()))
    result = await db.execute(query.order_by(EventLog.occurred_at.desc()).offset(skip).limit(limit))
    events = result.scalars().all()

    channel_names = await _fetch_channel_names(db, [e.camera_id for e in events])
    return EventListResponse(
        events=[_to_schema(e, channel_names.get(e.camera_id)) for e in events],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get("/events/search", response_model=EventListResponse)
async def search_events(
    q:          str = Query(..., min_length=1),
    channel_id: Optional[str] = Query(None),
    limit:      int = Query(10, ge=1, le=50),
    start_date: Optional[datetime] = Query(None),
    end_date:   Optional[datetime] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    cleaned_query, parsed_start, parsed_end, label = parse_time_expression(q)

    if start_date or end_date:
        active_start, active_end, applied_filter = start_date, end_date, None
    else:
        active_start, active_end, applied_filter = parsed_start, parsed_end, label

    embed_response = await _openai.embeddings.create(
        model="text-embedding-3-small",
        input=cleaned_query or q,
    )
    query_vector: list[float] = embed_response.data[0].embedding

    distance_col = EventLog.embedding.cosine_distance(query_vector).label("distance")
    stmt = (
        select(EventLog, distance_col)
        .where(EventLog.embedding.is_not(None))
        .order_by(distance_col)
        .limit(limit)
    )
    if channel_id:
        stmt = stmt.where(EventLog.camera_id == channel_id)
    if active_start:
        stmt = stmt.where(EventLog.occurred_at >= active_start)
    if active_end:
        stmt = stmt.where(EventLog.occurred_at <= active_end)

    rows = (await db.execute(stmt)).all()

    if not rows:
        return EventListResponse(
            events=[], total=0, skip=0, limit=limit, applied_filter=applied_filter
        )

    camera_ids    = [event.camera_id for event, _ in rows]
    channel_names = await _fetch_channel_names(db, camera_ids)

    return EventListResponse(
        events=[
            _to_schema(event, channel_names.get(event.camera_id), similarity=max(round(1 - distance, 4), 0.0))
            for event, distance in rows
        ],
        total=len(rows),
        skip=0,
        limit=limit,
        applied_filter=applied_filter,
    )


@router.get("/events/{event_id}", response_model=EventLogRead)
async def get_event(
    event_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    event = await db.get(EventLog, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="이벤트를 찾을 수 없습니다")

    channel_names = await _fetch_channel_names(db, [event.camera_id])
    return _to_schema(event, channel_names.get(event.camera_id))