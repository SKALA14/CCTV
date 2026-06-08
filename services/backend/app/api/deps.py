# services/backend/app/api/deps.py
"""FastAPI 공통 의존성. 인증 토큰 검증 및 역할 확인을 담당한다."""

from fastapi import Depends, HTTPException, Request

from app.api.auth import _validate_token


async def get_current_user(request: Request) -> dict:
    """httpOnly 쿠키에서 JWT를 읽고 검증한다. 미인증 시 401.

    반환값: {"sub": username, "role": role, "exp": ..., "bid": boot_id}
    """
    return await _validate_token(request)


async def require_admin(user: dict = Depends(get_current_user)) -> dict:
    """admin 역할만 허용한다. viewer 접근 시 403."""
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다")
    return user
