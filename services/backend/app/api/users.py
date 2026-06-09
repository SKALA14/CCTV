# services/backend/app/api/users.py
"""계정 관리 API. superadmin은 모든 현장, admin은 자기 현장 viewer만."""
import secrets
import string
import uuid
import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from passlib.context import CryptContext

from app.api.deps import get_current_user, require_admin
from app.db.session import get_db
from app.db.models import User, Site

logger = logging.getLogger(__name__)
router = APIRouter(tags=["users"])

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
_VALID_ROLES = {"admin", "viewer"}


def _generate_initial_password() -> str:
    """12자 무작위 비밀번호: 영대소문자 + 숫자 + 특수문자."""
    alphabet = string.ascii_letters + string.digits + "!@#$%"
    return "".join(secrets.choice(alphabet) for _ in range(12))


def _validate_password_strength(password: str) -> None:
    if len(password) < 8 or len(password) > 72:
        raise HTTPException(status_code=422, detail="비밀번호는 8자 이상 72자 이하여야 합니다.")
    if not any(c.isdigit() for c in password):
        raise HTTPException(status_code=422, detail="비밀번호에 숫자가 포함되어야 합니다.")
    if not any(c.isalpha() for c in password):
        raise HTTPException(status_code=422, detail="비밀번호에 영문자가 포함되어야 합니다.")


class UserCreate(BaseModel):
    username: str
    role:     str

    @field_validator("role")
    @classmethod
    def role_must_be_valid(cls, v):
        if v not in _VALID_ROLES:
            raise ValueError(f"role은 {_VALID_ROLES} 중 하나여야 합니다.")
        return v


class UserRead(BaseModel):
    id:                   str
    username:             str
    role:                 str
    site_id:              str | None
    must_change_password: bool


class UserUpdate(BaseModel):
    username: str | None = None
    role:     str | None = None

    @field_validator("role")
    @classmethod
    def role_must_be_valid(cls, v):
        if v is not None and v not in _VALID_ROLES:
            raise ValueError(f"role은 {_VALID_ROLES} 중 하나여야 합니다.")
        return v


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password:     str


async def _assert_site_access(
    site_id: uuid.UUID,
    current_user: User,
    db: AsyncSession,
) -> Site:
    """현재 사용자가 해당 현장에 접근 가능한지 확인. superadmin은 모두 허용."""
    site = await db.get(Site, site_id)
    if not site:
        raise HTTPException(status_code=404, detail="현장을 찾을 수 없습니다.")
    if current_user.role != "superadmin" and current_user.site_id != site_id:
        raise HTTPException(status_code=403, detail="해당 현장에 접근 권한이 없습니다.")
    return site


@router.post("/sites/{site_id}/users", status_code=201)
async def create_user(
    site_id: uuid.UUID,
    body: UserCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """계정 생성. superadmin은 admin/viewer 생성 가능. admin은 viewer만 생성 가능."""
    await _assert_site_access(site_id, current_user, db)
    if current_user.role not in ("admin", "superadmin"):
        raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다")
    if current_user.role == "admin" and body.role == "admin":
        raise HTTPException(status_code=403, detail="admin은 viewer 계정만 생성할 수 있습니다.")

    existing = await db.scalar(select(User).where(User.username == body.username))
    if existing:
        raise HTTPException(status_code=409, detail="이미 사용 중인 username입니다.")

    initial_password = _generate_initial_password()
    user = User(
        username=body.username,
        hashed_password=_pwd_context.hash(initial_password),
        role=body.role,
        site_id=site_id,
        must_change_password=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    logger.info("계정 생성: username=%s role=%s site_id=%s", user.username, user.role, site_id)

    return {
        "user": UserRead(
            id=str(user.id),
            username=user.username,
            role=user.role,
            site_id=str(user.site_id),
            must_change_password=user.must_change_password,
        ),
        "initial_password": initial_password,
    }


@router.get("/sites/{site_id}/users", response_model=list[UserRead])
async def list_users(
    site_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _assert_site_access(site_id, current_user, db)
    users = (await db.execute(
        select(User).where(User.site_id == site_id).order_by(User.username)
    )).scalars().all()
    return [
        UserRead(
            id=str(u.id),
            username=u.username,
            role=u.role,
            site_id=str(u.site_id),
            must_change_password=u.must_change_password,
        )
        for u in users
    ]


@router.patch("/sites/{site_id}/users/{user_id}", response_model=UserRead)
async def update_user(
    site_id: uuid.UUID,
    user_id: uuid.UUID,
    body: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    await _assert_site_access(site_id, current_user, db)
    user = await db.get(User, user_id)
    if not user or user.site_id != site_id:
        raise HTTPException(status_code=404, detail="계정을 찾을 수 없습니다.")
    if body.role is not None and current_user.role != "superadmin":
        raise HTTPException(status_code=403, detail="role 변경은 슈퍼어드민만 가능합니다.")
    if body.username is not None:
        dup = await db.scalar(
            select(User).where(User.username == body.username, User.id != user_id)
        )
        if dup:
            raise HTTPException(status_code=409, detail="이미 사용 중인 username입니다.")
        user.username = body.username
    if body.role is not None:
        user.role = body.role
    await db.commit()
    await db.refresh(user)
    return UserRead(
        id=str(user.id),
        username=user.username,
        role=user.role,
        site_id=str(user.site_id),
        must_change_password=user.must_change_password,
    )


@router.delete("/sites/{site_id}/users/{user_id}", status_code=204)
async def delete_user(
    site_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    await _assert_site_access(site_id, current_user, db)
    user = await db.get(User, user_id)
    if not user or user.site_id != site_id:
        raise HTTPException(status_code=404, detail="계정을 찾을 수 없습니다.")
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="자기 자신은 삭제할 수 없습니다.")
    await db.delete(user)
    await db.commit()


@router.post("/sites/{site_id}/users/{user_id}/reset-password")
async def reset_user_password(
    site_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _assert_site_access(site_id, current_user, db)
    if current_user.role not in ("admin", "superadmin"):
        raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다")
    user = await db.get(User, user_id)
    if not user or user.site_id != site_id:
        raise HTTPException(status_code=404, detail="계정을 찾을 수 없습니다.")
    if current_user.role == "admin" and user.role == "admin":
        raise HTTPException(status_code=403, detail="admin 계정의 비밀번호는 슈퍼어드민만 초기화할 수 있습니다.")
    new_password = _generate_initial_password()
    user.hashed_password      = _pwd_context.hash(new_password)
    user.must_change_password = True
    await db.commit()
    return {"new_password": new_password}


@router.patch("/users/me/password", status_code=204)
async def change_my_password(
    body: PasswordChangeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not _pwd_context.verify(body.current_password, current_user.hashed_password):
        raise HTTPException(status_code=401, detail="현재 비밀번호가 올바르지 않습니다.")
    if body.current_password == body.new_password:
        raise HTTPException(status_code=422, detail="새 비밀번호는 현재 비밀번호와 달라야 합니다.")
    _validate_password_strength(body.new_password)
    # current_user는 _validate_token 내부 세션에서 로드된 객체라 db 세션이 추적하지 않음.
    # db 세션에서 재조회해야 commit() 시 변경사항이 실제로 저장됨.
    user = await db.get(User, current_user.id)
    if user is None:
        raise HTTPException(status_code=404, detail="계정을 찾을 수 없습니다.")
    user.hashed_password      = _pwd_context.hash(body.new_password)
    user.must_change_password = False
    await db.commit()
