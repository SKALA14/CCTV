# services/backend/app/api/auth.py
"""JWT httpOnly 쿠키 인증.

로그인: DB 조회 + bcrypt 검증 → JWT 발급 (sub=user_id, role, site_id, bid)
검증: _validate_token — 쿠키 파싱 → 서명 검증 → boot_id 확인 → DB User 존재 확인 → site_id 일치 확인
로그아웃: 쿠키 삭제
"""
import logging
import uuid
from datetime import datetime, timedelta, timezone

import redis.asyncio as aioredis
from fastapi import APIRouter, HTTPException, Request, Response
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import select

from app.config import config
from app.db.session import AsyncSessionLocal
from app.db.models import Site, User

logger = logging.getLogger(__name__)

_ALGORITHM  = "HS256"
_BOOT_ID_KEY = "auth:boot_id"


def _client_ip(request: Request) -> str:
    """rate-limit 키: nginx 프록시 뒤에서 실제 클라이언트 IP를 X-Forwarded-For로 식별.
    헤더가 없으면 직접 피어 주소로 폴백.
    """
    xff = request.headers.get("X-Forwarded-For")
    if xff:
        return xff.split(",")[0].strip()
    return get_remote_address(request)


_limiter = Limiter(key_func=_client_ip)
router   = APIRouter(tags=["auth"])

_redis = aioredis.from_url(config.REDIS_URL, decode_responses=True)
_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# 존재하지 않는 username 로그인 시 타이밍 일정화를 위한 더미 검증용 정상 bcrypt 해시.
# 최초 사용 시 1회 생성(lazy) — 깨진 해시 상수를 쓰면 verify가 ValueError를 던져 500이 발생.
_dummy_hash: str | None = None


def _get_dummy_hash() -> str:
    global _dummy_hash
    if _dummy_hash is None:
        _dummy_hash = _pwd_context.hash("dummy_password_for_timing_safety")
    return _dummy_hash


# ──────────────────────────────────────────────────────────────────
# 내부 헬퍼
# ──────────────────────────────────────────────────────────────────

async def _get_boot_id() -> str:
    """Redis에서 boot_id 조회. 없으면 새로 생성해 저장."""
    bid = await _redis.get(_BOOT_ID_KEY)
    if not bid:
        bid = str(uuid.uuid4())
        await _redis.set(_BOOT_ID_KEY, bid)
    return bid


async def _create_token(
    user_id: uuid.UUID,
    username: str,
    role: str,
    site_id: uuid.UUID | None,
) -> str:
    """JWT 발급. sub=str(user_id), role, bid 포함. site_id는 None이면 생략."""
    boot_id = await _get_boot_id()
    expire  = datetime.now(timezone.utc) + timedelta(hours=config.JWT_EXPIRE_HOURS)
    payload: dict = {
        "sub":  str(user_id),
        "role": role,
        "exp":  expire,
        "bid":  boot_id,
    }
    if site_id is not None:
        payload["site_id"] = str(site_id)
    return jwt.encode(payload, config.AUTH_SECRET, algorithm=_ALGORITHM)


def _decode_token(token: str) -> dict:
    """JWT 서명 검증 + 디코딩. 실패 시 401."""
    try:
        return jwt.decode(token, config.AUTH_SECRET, algorithms=[_ALGORITHM])
    except JWTError as e:
        # 상세 사유는 서버 로그에만 — 클라이언트엔 일반 메시지(내부 정보 노출 방지)
        logger.warning("[auth] 토큰 디코딩 실패: %s", e)
        raise HTTPException(status_code=401, detail="유효하지 않은 토큰입니다")


async def _verify_credentials_db(username: str, password: str) -> User | None:
    """DB에서 username 조회 후 bcrypt 검증. 일치하면 User 반환, 아니면 None.

    bcrypt는 타이밍 일정 비교를 내부적으로 처리.
    입력이 72자를 초과하면 bcrypt가 무시하므로 앞단에서 길이 제한.
    """
    if len(password) > 72:
        return None
    async with AsyncSessionLocal() as session:
        user = await session.scalar(
            select(User).where(User.username == username)
        )
    if user is None:
        # timing 일정화: 사용자 없어도 정상 해시로 dummy 검증 수행 (응답시간 차로 계정 열거 방지)
        _pwd_context.verify("dummy", _get_dummy_hash())
        return None
    if not _pwd_context.verify(password, user.hashed_password):
        return None
    return user


async def _validate_token(request: Request) -> dict:
    """쿠키 JWT 검증 + DB User 존재 확인.

    반환 payload에 'db_user' 키로 User 객체 추가.
    - 쿠키 없음 / 서명 불일치 / boot_id 불일치 → 401
    - DB에 해당 user_id 없음 → 401 (삭제된 계정)
    - site_id 불일치 (role 변경 등) → 401
    """
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail="로그인이 필요합니다")

    payload = _decode_token(token)

    current_boot_id = await _redis.get(_BOOT_ID_KEY)
    if payload.get("bid") != current_boot_id:
        raise HTTPException(status_code=401, detail="세션이 만료됐습니다. 다시 로그인하세요.")

    async with AsyncSessionLocal() as session:
        user = await session.get(User, uuid.UUID(payload["sub"]))
    if user is None:
        raise HTTPException(status_code=401, detail="존재하지 않는 계정입니다.")

    payload_site_id = payload.get("site_id")
    user_site_id    = str(user.site_id) if user.site_id else None
    if payload_site_id != user_site_id:
        raise HTTPException(status_code=401, detail="세션이 유효하지 않습니다.")

    payload["db_user"] = user
    return payload


# ──────────────────────────────────────────────────────────────────
# 스키마
# ──────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str
    password: str


class UserInfo(BaseModel):
    user_id:              str
    username:             str
    role:                 str
    site_id:              str | None = None
    site_name:            str | None = None
    must_change_password: bool = False
    last_login:           str | None = None   # ISO8601 (Redis 기록값) — 계정 칩 "마지막 접속" 표시용


# ──────────────────────────────────────────────────────────────────
# 엔드포인트
# ──────────────────────────────────────────────────────────────────

@router.post("/auth/login", response_model=UserInfo)
@_limiter.limit("5/minute")
async def login(request: Request, body: LoginRequest, response: Response):
    if len(body.password) > 72:
        raise HTTPException(status_code=401, detail="아이디 또는 비밀번호가 올바르지 않습니다")

    user = await _verify_credentials_db(body.username, body.password)
    if user is None:
        logger.warning("[auth] 로그인 실패: username=%s", body.username)
        raise HTTPException(status_code=401, detail="아이디 또는 비밀번호가 올바르지 않습니다")

    site_name: str | None = None
    if user.site_id is not None:
        async with AsyncSessionLocal() as session:
            site = await session.get(Site, user.site_id)
            site_name = site.name if site else None

    token = await _create_token(
        user_id=user.id,
        username=user.username,
        role=user.role,
        site_id=user.site_id,
    )
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=config.COOKIE_SECURE,
        samesite="lax",
        max_age=config.JWT_EXPIRE_HOURS * 3600,
    )
    logger.info("[auth] 로그인 성공: username=%s role=%s", user.username, user.role)
    try:
        await _redis.set(
            f"user:last_login:{user.id}",
            datetime.now(timezone.utc).isoformat(),
        )
    except Exception as e:
        logger.warning("[auth] last_login 기록 실패: %s", e)
    last_login: str | None = None
    try:
        last_login = await _redis.get(f"user:last_login:{user.id}")
    except Exception:
        last_login = None
    return UserInfo(
        user_id=str(user.id),
        username=user.username,
        role=user.role,
        site_id=str(user.site_id) if user.site_id else None,
        site_name=site_name,
        must_change_password=user.must_change_password,
        last_login=last_login,
    )


@router.post("/auth/logout")
async def logout(response: Response):
    response.delete_cookie("access_token")
    return {"message": "로그아웃 되었습니다"}


@router.get("/auth/me", response_model=UserInfo)
async def me(request: Request):
    payload = await _validate_token(request)
    user: User = payload["db_user"]
    site_name: str | None = None
    if user.site_id is not None:
        async with AsyncSessionLocal() as session:
            site = await session.get(Site, user.site_id)
            site_name = site.name if site else None
    last_login: str | None = None
    try:
        last_login = await _redis.get(f"user:last_login:{user.id}")
    except Exception:
        last_login = None
    return UserInfo(
        user_id=str(user.id),
        username=user.username,
        role=user.role,
        site_id=str(user.site_id) if user.site_id else None,
        site_name=site_name,
        must_change_password=user.must_change_password,
        last_login=last_login,
    )
