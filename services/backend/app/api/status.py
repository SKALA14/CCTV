# services/backend/app/api/status.py
"""admin 전용 모니터링 API — 현장 요약/기기 상태/계정 현황."""
import time
import uuid
import logging
from datetime import datetime, timezone, timedelta

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin, get_current_user
from app.config import config
from app.db.session import get_db
from app.db.models import Site, User, CctvChannel, EventLog

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/status", tags=["status"])

_KST = timezone(timedelta(hours=9))   # "오늘" 날짜 경계 계산용 (UTC+9)
_ONLINE_THRESHOLD_SEC = 30.0
# frames 스트림은 카메라당 ~2fps(SAMPLE_FPS=2)·채널 ≤4개로 샘플링되므로
# 최근 2000개 엔트리는 약 4분 분량 → 30초 online 임계값을 충분히 커버한다.
# (카메라 수/프레임레이트가 크게 늘면 per-camera heartbeat 키로 전환 필요)
_FRAMES_SCAN_COUNT = 2000

_status_redis: aioredis.Redis | None = None


def _get_redis() -> aioredis.Redis:
    global _status_redis
    if _status_redis is None:
        _status_redis = aioredis.from_url(config.REDIS_URL, decode_responses=True)
    return _status_redis


def _latest_frame_ts(entries: list[dict]) -> dict[tuple[str, str], float]:
    """frames 스트림 엔트리들에서 (site_id, camera_id)별 최신 timestamp 추출."""
    out: dict[tuple[str, str], float] = {}
    for e in entries:
        sid = e.get("site_id", "")
        cid = e.get("camera_id", "")
        try:
            ts = float(e.get("timestamp", "0"))
        except (ValueError, TypeError):
            continue
        key = (sid, cid)
        if key not in out or ts > out[key]:
            out[key] = ts
    return out


def _is_online(last_ts: float | None, now: float, threshold: float = _ONLINE_THRESHOLD_SEC) -> bool:
    """마지막 프레임 수신이 threshold초 이내면 online."""
    return last_ts is not None and (now - last_ts) <= threshold


def _today_start() -> datetime:
    # "오늘"은 한국 시간(KST) 자정 기준. tz-aware라 UTC로 저장된 occurred_at과 정확히 비교됨.
    now = datetime.now(_KST)
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


@router.get("/health")
async def health(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),   # 전 계정(보기 권한) — 사이드바 상태 pill용
) -> dict:
    """자기 현장 채널 온라인 요약 {online, total}. frames 스트림 최신 프레임 기준."""
    channels = (await db.execute(
        select(CctvChannel).where(CctvChannel.site_id == current_user.site_id)
    )).scalars().all()
    total = len(channels)
    if total == 0:
        return {"online": 0, "total": 0}
    raw = await _get_redis().xrevrange(config.FRAMES_STREAM, count=_FRAMES_SCAN_COUNT)
    latest = _latest_frame_ts([fields for _id, fields in raw])
    now = time.time()
    sid = str(current_user.site_id)
    online = sum(1 for ch in channels if _is_online(latest.get((sid, ch.camera_id)), now))
    return {"online": online, "total": total}


@router.get("/overview")
async def overview(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> list[dict]:
    """구역별 요약: 카메라 수, 오늘 이벤트 수. (자기 현장만)"""
    channels = (await db.execute(
        select(CctvChannel).where(CctvChannel.site_id == current_user.site_id)
    )).scalars().all()

    today = _today_start()
    redis = _get_redis()
    site_id_str = str(current_user.site_id)

    zone_cameras: dict[str, list[str]] = {}
    for ch in channels:
        zone = await redis.get(f"camera:{site_id_str}:{ch.camera_id}:zone") or "미지정"
        zone_cameras.setdefault(zone, []).append(ch.camera_id)

    result = []
    for zone_name in sorted(zone_cameras, key=lambda z: (z == "미지정", z)):
        camera_ids = zone_cameras[zone_name]
        event_count = await db.scalar(
            select(func.count()).select_from(EventLog)
            .where(EventLog.site_id == current_user.site_id)
            .where(EventLog.camera_id.in_(camera_ids))
            .where(EventLog.occurred_at >= today)
        ) or 0
        result.append({
            "zone": zone_name,
            "camera_count": len(camera_ids),
            "today_event_count": event_count,
        })
    return result


@router.get("/devices")
async def devices(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> list[dict]:
    """CCTV별 온라인 상태 + 구역. (자기 현장만)"""
    channels = (await db.execute(
        select(CctvChannel)
        .where(CctvChannel.site_id == current_user.site_id)
        .order_by(CctvChannel.camera_id)
    )).scalars().all()

    raw = await _get_redis().xrevrange(config.FRAMES_STREAM, count=_FRAMES_SCAN_COUNT)
    entries = [fields for _id, fields in raw]
    latest = _latest_frame_ts(entries)
    now = time.time()
    site_id_str = str(current_user.site_id)
    redis = _get_redis()

    result = []
    for ch in channels:
        key = (site_id_str, ch.camera_id)
        last_ts = latest.get(key)
        zone = await redis.get(f"camera:{site_id_str}:{ch.camera_id}:zone") or "미지정"
        result.append({
            "zone": zone,
            "camera_id": ch.camera_id,
            "camera_name": ch.camera_name,
            "source_type": ch.source_type,
            "online": _is_online(last_ts, now),
            "last_seen": datetime.fromtimestamp(last_ts, tz=timezone.utc).isoformat() if last_ts else None,
        })
    return result


@router.get("/today-events")
async def today_events(
    zone: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> list[dict]:
    """오늘(KST) 이벤트 목록 — 구역 필터 지원."""
    today = _today_start()
    site_id_str = str(current_user.site_id)
    redis = _get_redis()

    camera_ids: list[str] | None = None
    if zone is not None:
        channels = (await db.execute(
            select(CctvChannel).where(CctvChannel.site_id == current_user.site_id)
        )).scalars().all()
        camera_ids = [
            ch.camera_id for ch in channels
            if (await redis.get(f"camera:{site_id_str}:{ch.camera_id}:zone") or "미지정") == zone
        ]
        if not camera_ids:
            return []

    query = (
        select(EventLog)
        .where(EventLog.site_id == current_user.site_id)
        .where(EventLog.occurred_at >= today)
        .order_by(EventLog.occurred_at.desc())
        .limit(300)
    )
    if camera_ids is not None:
        query = query.where(EventLog.camera_id.in_(camera_ids))

    rows = (await db.execute(query)).scalars().all()
    return [
        {
            "event_id":     str(e.event_id),
            "occurred_at":  e.occurred_at.isoformat(),
            "camera_id":    e.camera_id,
            "camera_name":  e.camera_name or e.camera_id,
            "event_type":   e.event_type,
            "danger_level": e.danger_level,
            "pipeline":     e.pipeline,
        }
        for e in rows
    ]


@router.get("/accounts")
async def accounts(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> list[dict]:
    """계정 현황 — role, 초기비번 여부, 마지막 로그인. (자기 현장만)"""
    rows = (await db.execute(
        select(User, Site.name)
        .join(Site, Site.id == User.site_id)
        .where(User.site_id == current_user.site_id)
        .order_by(User.username)
    )).all()
    redis = _get_redis()
    # 마지막 로그인은 MGET 한 번으로 일괄 조회 (계정 수만큼 라운드트립 방지)
    keys = [f"user:last_login:{user.id}" for user, _ in rows]
    last_logins = await redis.mget(keys) if keys else []
    result = []
    for (user, site_name), last_login in zip(rows, last_logins):
        result.append({
            "username": user.username,
            "role": user.role,
            "site_name": site_name,
            "must_change_password": user.must_change_password,
            "last_login": last_login,
        })
    return result


@router.get("/sites/{site_id}/today-events")
async def site_today_events(
    site_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> list[dict]:
    """현장의 오늘(KST) 이벤트 목록 — 발생 시각 내림차순. '오늘 이벤트' 드릴다운용. (자기 현장만)"""
    if site_id != current_user.site_id:
        raise HTTPException(status_code=404, detail="현장을 찾을 수 없습니다.")
    today = _today_start()
    rows = (await db.execute(
        select(EventLog)
        .where(EventLog.site_id == site_id)
        .where(EventLog.occurred_at >= today)
        .order_by(EventLog.occurred_at.desc())
        .limit(300)
    )).scalars().all()
    return [
        {
            "event_id":    str(e.event_id),
            "occurred_at": e.occurred_at.isoformat(),
            "camera_id":   e.camera_id,
            "camera_name": e.camera_name or e.camera_id,
            "event_type":  e.event_type,
            "danger_level": e.danger_level,
            "pipeline":    e.pipeline,
            "description": e.description,
        }
        for e in rows
    ]
