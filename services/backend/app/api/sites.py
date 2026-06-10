# services/backend/app/api/sites.py
"""현장(Site) 관리 API. admin 전용. 현장은 보통 설치 시 seed되며, 추가 현장이 필요할 때 admin이 관리한다."""
import uuid
import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin
from app.db.session import get_db
from app.db.models import Site, User, CctvChannel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/sites", tags=["sites"])


class SiteCreate(BaseModel):
    name: str


class SiteUpdate(BaseModel):
    name: str


class SiteRead(BaseModel):
    id:         str
    name:       str
    user_count: int = 0


@router.post("", status_code=201, response_model=SiteRead)
async def create_site(
    body: SiteCreate,
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_admin),
):
    if await db.scalar(select(Site).where(Site.name == body.name)):
        raise HTTPException(status_code=409, detail="이미 존재하는 현장 이름입니다.")
    site = Site(name=body.name)
    db.add(site)
    await db.commit()
    await db.refresh(site)
    return SiteRead(id=str(site.id), name=site.name)


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


@router.patch("/{site_id}", response_model=SiteRead)
async def update_site(
    site_id: uuid.UUID,
    body: SiteUpdate,
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_admin),
):
    site = await db.get(Site, site_id)
    if not site:
        raise HTTPException(status_code=404, detail="현장을 찾을 수 없습니다.")
    duplicate = await db.scalar(
        select(Site).where(Site.name == body.name, Site.id != site_id)
    )
    if duplicate:
        raise HTTPException(status_code=409, detail="이미 존재하는 현장 이름입니다.")
    site.name = body.name
    await db.commit()
    await db.refresh(site)
    return SiteRead(id=str(site.id), name=site.name)


@router.delete("/{site_id}", status_code=204)
async def delete_site(
    site_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_admin),
):
    """현장 삭제. 연결된 채널·유저는 CASCADE 삭제됨."""
    site = await db.get(Site, site_id)
    if not site:
        raise HTTPException(status_code=404, detail="현장을 찾을 수 없습니다.")
    channels = (await db.execute(
        select(CctvChannel).where(CctvChannel.site_id == site_id)
    )).scalars().all()
    await db.delete(site)
    await db.commit()
    logger.info("현장 삭제: site_id=%s channels=%d", site_id, len(channels))
