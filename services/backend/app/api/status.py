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

from app.api.deps import require_admin
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


@router.get("/overview")
async def overview(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> list[dict]:
    """현장 요약: 카메라 수, 오늘 이벤트 수·위험도 분포, 계정 수. (자기 현장만)"""
    sites = (await db.execute(
        select(Site).where(Site.id == current_user.site_id).order_by(Site.name)
    )).scalars().all()
    today = _today_start()
    result = []
    for site in sites:
        cam_count = await db.scalar(
            select(func.count()).select_from(CctvChannel).where(CctvChannel.site_id == site.id)
        )
        acct_count = await db.scalar(
            select(func.count()).select_from(User).where(User.site_id == site.id)
        )
        rows = (await db.execute(
            select(EventLog.danger_level, func.count())
            .where(EventLog.site_id == site.id)
            .where(EventLog.occurred_at >= today)
            .group_by(EventLog.danger_level)
        )).all()
        danger = {level: cnt for level, cnt in rows}
        result.append({
            "site_id": str(site.id),
            "name": site.name,
            "camera_count": cam_count or 0,
            "account_count": acct_count or 0,
            "today_event_count": sum(danger.values()),
            "danger_breakdown": danger,
        })
    return result


@router.get("/devices")
async def devices(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> list[dict]:
    """CCTV별 온라인 상태 — frames 스트림 최신 프레임 기준. (자기 현장만)"""
    channels = (await db.execute(
        select(CctvChannel, Site.name)
        .join(Site, Site.id == CctvChannel.site_id)
        .where(CctvChannel.site_id == current_user.site_id)
        .order_by(Site.name, CctvChannel.camera_id)
    )).all()

    raw = await _get_redis().xrevrange(config.FRAMES_STREAM, count=_FRAMES_SCAN_COUNT)
    entries = [fields for _id, fields in raw]
    latest = _latest_frame_ts(entries)
    now = time.time()

    result = []
    for ch, site_name in channels:
        key = (str(ch.site_id), ch.camera_id)
        last_ts = latest.get(key)
        result.append({
            "site_name": site_name,
            "camera_id": ch.camera_id,
            "camera_name": ch.camera_name,
            "source_type": ch.source_type,
            "online": _is_online(last_ts, now),
            "last_seen": datetime.fromtimestamp(last_ts, tz=timezone.utc).isoformat() if last_ts else None,
        })
    return result


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
