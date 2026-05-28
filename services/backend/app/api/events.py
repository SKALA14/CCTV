import asyncio
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from openai import AsyncOpenAI
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
from app.db.session import get_db
from app.db.models import EventLog, CctvChannel
from app.api.schemas import EventLogRead, EventListResponse
from app.api.time_parser import parse_time_expression
from app.api.query_expander import expand_query

router = APIRouter()
_openai = AsyncOpenAI()


def _to_schema(
    event: EventLog,
    channel_name: str | None = None,
    similarity: float | None = None,
    incident_count: int = 1,
    incident_last_at: datetime | None = None,
) -> EventLogRead:
    return EventLogRead(
        id=event.event_id,
        channel_id=event.camera_id,
        # 우선순위: 이벤트 발생 시점 채널명(스냅샷) > 현재 채널명(lookup) > camera_id
        channel_name=event.camera_name or channel_name or event.camera_id,
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
        snapshot_urls=event.snapshot_urls,
        clip_url=event.clip_url,
        source_path=event.source_path,
        occurred_at=event.occurred_at,
        created_at=event.created_at,
        similarity=similarity,
        incident_count=incident_count,
        incident_last_at=incident_last_at,
    )


def _group_into_incidents(events: list[EventLog]) -> list[dict]:
    """DESC 정렬된 이벤트들을 (camera_id, event_type) + 시간 간격 기준으로 묶는다.

    각 incident dict:
      - representative: 가장 먼저 발생한 이벤트 (= 시간순 earliest)
      - count: 묶인 이벤트 수
      - last_at: 가장 늦은 발생 시각
      - events: 묶인 이벤트들 전체 (검색 점수 계산 등에 사용)
    결과는 last_at DESC로 정렬된다.
    """
    if not events:
        return []

    open_incidents: dict[tuple[str, str], dict] = {}
    closed: list[dict] = []

    for e in events:  # DESC 가정
        key = (e.camera_id, e.event_type)
        cur = open_incidents.get(key)
        if cur is not None:
            gap = (cur["earliest"].occurred_at - e.occurred_at).total_seconds()
            if gap < config.INCIDENT_GAP_SEC:
                cur["earliest"] = e
                cur["events"].append(e)
                continue
            closed.append(cur)
        open_incidents[key] = {
            "earliest": e,
            "latest_at": e.occurred_at,
            "events": [e],
        }

    closed.extend(open_incidents.values())
    closed.sort(key=lambda i: i["latest_at"], reverse=True)
    return [
        {
            "representative": i["earliest"],
            "count": len(i["events"]),
            "last_at": i["latest_at"],
            "events": i["events"],
        }
        for i in closed
    ]


def _incident_last_at(count: int, last_at: datetime) -> datetime | None:
    """단일 이벤트(count=1)면 None 반환 — FE에서 occurred_at과 동일하다는 의미."""
    return last_at if count > 1 else None


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

    # 그룹화를 위해 충분한 raw event를 fetch한 후 incident 기준으로 페이지네이션
    fetch_limit = min(max(limit * 10, 200), 1000)
    raw_result = await db.execute(
        query.order_by(EventLog.occurred_at.desc()).limit(fetch_limit)
    )
    raw_events = raw_result.scalars().all()

    incidents = _group_into_incidents(raw_events)
    total = len(incidents)
    page = incidents[skip:skip + limit]

    channel_names = await _fetch_channel_names(
        db, [inc["representative"].camera_id for inc in page]
    )
    return EventListResponse(
        events=[
            _to_schema(
                inc["representative"],
                channel_names.get(inc["representative"].camera_id),
                incident_count=inc["count"],
                incident_last_at=_incident_last_at(inc["count"], inc["last_at"]),
            )
            for inc in page
        ],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get("/events/search", response_model=EventListResponse)
async def search_events(
    q:               str  = Query(..., min_length=1),
    channel_id:      Optional[str]      = Query(None),
    limit:           int  = Query(10, ge=1, le=50),
    start_date:      Optional[datetime] = Query(None),
    end_date:        Optional[datetime] = Query(None),
    skip_time_parse: bool = Query(False),
    db: AsyncSession = Depends(get_db),
):
    if skip_time_parse:
        cleaned_query, active_start, active_end, applied_filter = q, None, None, None
    else:
        cleaned_query, parsed_start, parsed_end, label = parse_time_expression(q)
        if start_date or end_date:
            active_start, active_end, applied_filter = start_date, end_date, None
        else:
            active_start, active_end, applied_filter = parsed_start, parsed_end, label

    base_query = cleaned_query or q
    variants = await expand_query(base_query)
    embed_responses = await asyncio.gather(*[
        _openai.embeddings.create(model="text-embedding-3-small", input=v)
        for v in variants
    ])
    query_vectors: list[list[float]] = [r.data[0].embedding for r in embed_responses]

    # 그룹화 후 limit를 채우려면 충분한 후보가 필요
    candidate_fetch_n = max(limit * 10, 100)

    all_candidates: dict[str, tuple] = {}
    for qv in query_vectors:
        dist_expr = EventLog.embedding.cosine_distance(qv)
        stmt = (
            select(EventLog, dist_expr.label("distance"))
            .where(EventLog.embedding.is_not(None))
            .where(dist_expr < 0.65)
            .order_by(dist_expr)
            .limit(candidate_fetch_n)
        )
        if channel_id:
            stmt = stmt.where(EventLog.camera_id == channel_id)
        if active_start:
            stmt = stmt.where(EventLog.occurred_at >= active_start)
        if active_end:
            stmt = stmt.where(EventLog.occurred_at <= active_end)

        for event, dist in (await db.execute(stmt)).all():
            eid = str(event.event_id)
            if eid not in all_candidates or dist < all_candidates[eid][1]:
                all_candidates[eid] = (event, dist)

    if not all_candidates:
        return EventListResponse(
            events=[], total=0, skip=0, limit=limit, applied_filter=applied_filter
        )

    # event_id → distance 매핑 (incident별 best distance 계산용)
    dist_by_id = {str(e.event_id): d for e, d in all_candidates.values()}

    # 시간순(DESC)으로 정렬해 incident 그룹화
    by_time = sorted(
        (e for e, _ in all_candidates.values()),
        key=lambda e: e.occurred_at,
        reverse=True,
    )
    incidents = _group_into_incidents(by_time)

    # 각 incident의 best (최소) distance로 점수화
    scored = []
    for inc in incidents:
        best_dist = min(dist_by_id[str(e.event_id)] for e in inc["events"])
        scored.append((inc, best_dist))

    # best distance ASC로 정렬 후 상위 limit
    scored.sort(key=lambda x: x[1])
    top = scored[:limit]

    channel_names = await _fetch_channel_names(
        db, [inc["representative"].camera_id for inc, _ in top]
    )

    return EventListResponse(
        events=[
            _to_schema(
                inc["representative"],
                channel_names.get(inc["representative"].camera_id),
                similarity=max(round(1 - dist, 4), 0.0),
                incident_count=inc["count"],
                incident_last_at=_incident_last_at(inc["count"], inc["last_at"]),
            )
            for inc, dist in top
        ],
        total=len(scored),
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