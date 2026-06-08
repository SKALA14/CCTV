# services/backend/app/api/auth.py
"""JWT 기반 인증. 로그인/로그아웃/현재 사용자 엔드포인트와 토큰 유틸을 제공한다."""

import logging
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import redis.asyncio as aioredis
from fastapi import APIRouter, HTTPException, Request, Response
from jose import JWTError, jwt
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import config

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

_ALGORITHM = "HS256"

# rate limiter — 로그인 브루트포스 방어 (분당 5회)
_limiter = Limiter(key_func=get_remote_address)

# Redis 클라이언트 — boot_id 저장소
_redis = aioredis.from_url(config.REDIS_URL, decode_responses=True)
_BOOT_ID_KEY = "auth:boot_id"


# --- JWT 유틸 ---

async def _get_boot_id() -> str:
    """서버 부팅 식별자. Redis에 없으면 생성해 저장.

    SET NX(set-if-not-exists)로 동시 기동 시 race condition 방지.
    boot_id는 TTL 없음 — volume 삭제 시에만 초기화 의도.
    """
    boot_id = await _redis.get(_BOOT_ID_KEY)
    if not boot_id:
        new_id = str(uuid.uuid4())
        await _redis.set(_BOOT_ID_KEY, new_id, nx=True)
        boot_id = await _redis.get(_BOOT_ID_KEY)   # 경쟁에서 진 경우 상대방 값을 읽음
    return boot_id


async def _create_token(username: str, role: str) -> str:
    """username과 role을 담은 JWT를 발급한다. boot_id(bid)를 클레임으로 포함한다."""
    boot_id = await _get_boot_id()
    expire = datetime.now(timezone.utc) + timedelta(hours=config.JWT_EXPIRE_HOURS)
    payload = {"sub": username, "role": role, "exp": expire, "bid": boot_id}
    return jwt.encode(payload, config.AUTH_SECRET, algorithm=_ALGORITHM)


def _decode_token(token: str) -> dict:
    """JWT를 검증하고 payload를 반환한다. 유효하지 않으면 401을 발생시킨다."""
    try:
        return jwt.decode(token, config.AUTH_SECRET, algorithms=[_ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=401, detail="유효하지 않은 인증 토큰입니다")


async def _validate_token(request: Request) -> dict:
    """쿠키 JWT 검증 공통 헬퍼. me 엔드포인트와 deps.get_current_user 양쪽에서 사용.

    - 쿠키 없음 → 401
    - 서명 불일치/만료 → 401
    - boot_id 불일치 (volume 삭제 후 스테일 토큰) → 401
    - 정상 → payload dict 반환
    """
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail="로그인이 필요합니다")
    payload = _decode_token(token)
    current_boot_id = await _redis.get(_BOOT_ID_KEY)
    if payload.get("bid") != current_boot_id:
        raise HTTPException(status_code=401, detail="세션이 만료됐습니다. 다시 로그인하세요.")
    return payload


def _verify_credentials(username: str, password: str) -> str | None:
    """username/password를 .env 설정과 대조한다. 일치하면 role을 반환, 아니면 None.

    secrets.compare_digest: 타이밍 공격 방어를 위한 상수시간 비교
    """
    if (secrets.compare_digest(username, config.ADMIN_USERNAME)
            and secrets.compare_digest(password, config.ADMIN_PASSWORD)):
        return "admin"
    if (secrets.compare_digest(username, config.VIEWER_USERNAME)
            and secrets.compare_digest(password, config.VIEWER_PASSWORD)):
        return "viewer"
    return None


# --- 요청/응답 스키마 ---

class LoginRequest(BaseModel):
    username: str
    password: str


class UserInfo(BaseModel):
    username: str
    role:     str


# --- 엔드포인트 ---

@router.post("/login", response_model=UserInfo)
@_limiter.limit("5/minute")
async def login(request: Request, body: LoginRequest, response: Response):
    """로그인. 성공 시 JWT를 httpOnly 쿠키로 설정하고 사용자 정보를 반환한다."""
    role = _verify_credentials(body.username, body.password)
    if role is None:
        logger.warning("[auth] 로그인 실패: username=%s", body.username)
        raise HTTPException(status_code=401, detail="아이디 또는 비밀번호가 올바르지 않습니다")

    token = await _create_token(body.username, role)
    # httpOnly=True: JavaScript에서 접근 불가 (XSS 방어)
    # samesite="lax": CSRF 방어
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=config.COOKIE_SECURE,  # 운영(.env COOKIE_SECURE=true)에서 HTTPS 전용
        samesite="lax",
        max_age=config.JWT_EXPIRE_HOURS * 3600,
    )
    logger.info("[auth] 로그인 성공: username=%s role=%s", body.username, role)
    return UserInfo(username=body.username, role=role)


@router.post("/logout")
async def logout(response: Response):
    """로그아웃. 쿠키를 삭제한다."""
    response.delete_cookie(key="access_token")
    return {"message": "로그아웃 되었습니다"}


@router.get("/me", response_model=UserInfo)
async def me(request: Request):
    """현재 로그인된 사용자 정보를 반환한다. 미인증 시 401."""
    payload = await _validate_token(request)
    return UserInfo(username=payload["sub"], role=payload["role"])
