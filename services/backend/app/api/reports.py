# services/backend/app/api/reports.py
"""리포트 API — 자기 현장의 안전 이벤트 집계 (admin). 리포트 탭의 미니차트용."""
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin
from app.db.session import get_db
from app.db.models import EventLog, User

router = APIRouter(prefix="/reports", tags=["reports"])

_KST = timezone(timedelta(hours=9))


def _to_kst(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(_KST)


@router.get("/summary")
async def summary(
    days: int = Query(7, ge=1, le=90),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> dict:
    """자기 현장 최근 N일(KST) 이벤트 집계.

    반환: total, danger_breakdown, by_day[{date,count}], by_hour[{hour,count}], top_cameras.
    기간이 현장 단위라 행 수가 제한적 → Python 집계로 DB 비종속 처리.
    """
    sid = current_user.site_id
    now = datetime.now(_KST)
    start = (now - timedelta(days=days - 1)).replace(hour=0, minute=0, second=0, microsecond=0)

    rows = (await db.execute(
        select(EventLog.occurred_at, EventLog.danger_level, EventLog.camera_name)
        .where(EventLog.site_id == sid)
        .where(EventLog.occurred_at >= start)
    )).all()

    danger_breakdown: dict[str, int] = {}
    by_day: dict[str, int] = {}
    by_hour = [0] * 24
    by_camera: dict[str, int] = {}

    for occurred_at, danger, cam in rows:
        kst = _to_kst(occurred_at)
        danger = danger or "none"
        danger_breakdown[danger] = danger_breakdown.get(danger, 0) + 1
        day_key = kst.strftime("%m-%d")
        by_day[day_key] = by_day.get(day_key, 0) + 1
        by_hour[kst.hour] += 1
        if cam:
            by_camera[cam] = by_camera.get(cam, 0) + 1

    # 빈 날도 0으로 채워 연속 시계열 생성
    days_series = []
    for i in range(days):
        key = (start + timedelta(days=i)).strftime("%m-%d")
        days_series.append({"date": key, "count": by_day.get(key, 0)})

    top_cameras = sorted(
        ({"camera": k, "count": v} for k, v in by_camera.items()),
        key=lambda x: -x["count"],
    )[:5]

    return {
        "days": days,
        "total": len(rows),
        "danger_breakdown": danger_breakdown,
        "by_day": days_series,
        "by_hour": [{"hour": h, "count": by_hour[h]} for h in range(24)],
        "top_cameras": top_cameras,
    }
