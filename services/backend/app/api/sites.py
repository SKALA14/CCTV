# services/backend/app/api/sites.py
"""현장(Site) 조회 API. 현장은 설치 시 seed로 등록되며 런타임에 생성/수정/삭제하지 않는다."""
import uuid
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin
from app.db.session import get_db
from app.db.models import Site, User

router = APIRouter(prefix="/sites", tags=["sites"])


class SiteRead(BaseModel):
    id:         str
    name:       str
    user_count: int = 0


@router.get("", response_model=list[SiteRead])
async def list_sites(
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_admin),
):
    sites = (await db.execute(select(Site).order_by(Site.name))).scalars().all()
    result = []
    for site in sites:
        cnt = await db.scalar(
            select(func.count()).select_from(User).where(User.site_id == site.id)
        )
        result.append(SiteRead(id=str(site.id), name=site.name, user_count=cnt or 0))
    return result


@router.get("/{site_id}", response_model=SiteRead)
async def get_site(
    site_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_admin),
):
    site = await db.get(Site, site_id)
    if not site:
        raise HTTPException(status_code=404, detail="현장을 찾을 수 없습니다.")
    cnt = await db.scalar(
        select(func.count()).select_from(User).where(User.site_id == site.id)
    )
    return SiteRead(id=str(site.id), name=site.name, user_count=cnt or 0)
