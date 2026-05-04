# 이벤트 조회 REST API. 목록 조회, 의미 기반 검색, 단건 조회 엔드포인트를 제공한다.

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from openai import AsyncOpenAI
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import EventLog, CctvChannel
from app.schemas import EventLogRead, EventListResponse

router = APIRouter()
_openai = AsyncOpenAI()


# EventLog ORM 객체를 프론트엔드 필드명에 맞는 EventLogRead 스키마로 변환한다.
def _to_schema(event: EventLog, channel_name: str | None = None) -> EventLogRead:
    return EventLogRead(
        id=event.event_id,
        channel_id=event.camera_id,
        channel_name=channel_name or event.camera_id,
        pipeline=event.pipeline,
        event_type=event.event_type,
        danger_level=event.danger_level,
        reason=event.description,
        confidence=None,
        vlm_confidence=None,
        pose_event=None,
        thumbnail_url=None,
        clip_url=None,
        source_path=event.source_path,
        occurred_at=event.occurred_at,
        created_at=event.created_at,
    )


# camera_id 목록으로 cctv_channels를 조회해 {camera_id: camera_name} 딕셔너리를 반환한다.
async def _fetch_channel_names(db: AsyncSession, camera_ids: list[str]) -> dict[str, str]:
    result = await db.execute(
        select(CctvChannel).where(CctvChannel.camera_id.in_(camera_ids))
    )
    return {ch.camera_id: ch.camera_name for ch in result.scalars().all()}


# 이벤트 목록을 반환한다. channel_id/pipeline/event_type/danger_level 필터와 페이지네이션을 지원한다.
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


# 검색어를 임베딩으로 변환한 뒤 pgvector 코사인 유사도로 의미적으로 유사한 이벤트를 반환한다.
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

    query = select(EventLog).where(EventLog.embedding.isnot(None))
    if channel_id:
        query = query.where(EventLog.camera_id == channel_id)

    result = await db.execute(
        query.order_by(EventLog.embedding.cosine_distance(query_vector)).limit(limit)
    )
    events = result.scalars().all()

    channel_names = await _fetch_channel_names(db, [e.camera_id for e in events])
    return EventListResponse(
        events=[_to_schema(e, channel_names.get(e.camera_id)) for e in events],
        total=len(events),
        skip=0,
        limit=limit,
    )


# event_id로 단건 이벤트를 조회한다. 존재하지 않으면 404를 반환한다.
@router.get("/events/{event_id}", response_model=EventLogRead)
async def get_event(
    event_id: str,
    db: AsyncSession = Depends(get_db),
):
    event = await db.get(EventLog, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="이벤트를 찾을 수 없습니다")

    channel_names = await _fetch_channel_names(db, [event.camera_id])
    return _to_schema(event, channel_names.get(event.camera_id))
