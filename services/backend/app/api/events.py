import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from openai import AsyncOpenAI
from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.db.models import EventLog, CctvChannel
from app.api.schemas import EventLogRead, EventListResponse

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
    db: AsyncSession = Depends(get_db),
):
    response = await _openai.embeddings.create(
        model="text-embedding-3-small",
        input=q,
    )
    query_vector = response.data[0].embedding

    where_clause = "WHERE embedding IS NOT NULL"
    params: dict = {"vec": str(query_vector), "limit": limit}
    if channel_id:
        where_clause += " AND camera_id = :channel_id"
        params["channel_id"] = channel_id

    rows = await db.execute(
        text(f"""
            SELECT event_id,
                   (embedding <=> CAST(:vec AS vector)) AS distance
            FROM event_logs
            {where_clause}
            ORDER BY distance
            LIMIT :limit
        """),
        params,
    )
    id_dist = {str(r.event_id): r.distance for r in rows}

    if not id_dist:
        return EventListResponse(events=[], total=0, skip=0, limit=limit)

    result = await db.execute(
        select(EventLog).where(EventLog.event_id.in_([uuid.UUID(k) for k in id_dist]))
    )
    events_map = {str(e.event_id): e for e in result.scalars().all()}
    ordered = [events_map[k] for k in id_dist if k in events_map]

    channel_names = await _fetch_channel_names(db, [e.camera_id for e in ordered])
    return EventListResponse(
        events=[
            _to_schema(e, channel_names.get(e.camera_id), similarity=round(1 - id_dist[str(e.event_id)], 4))
            for e in ordered
        ],
        total=len(ordered),
        skip=0,
        limit=limit,
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