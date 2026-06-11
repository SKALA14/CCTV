# services/backend/app/api/deps.py
"""FastAPI 공통 의존성. 인증 토큰 검증 및 역할 확인을 담당한다."""
from fastapi import Depends, HTTPException, Request
from app.api.auth import _validate_token
from app.db.models import User


async def get_current_user(request: Request) -> User:
    """JWT 검증 + DB User 반환. 미인증·삭제된 계정·site 불일치 시 401."""
    payload = await _validate_token(request)
    return payload["db_user"]


async def require_admin(user: User = Depends(get_current_user)) -> User:
    """admin만 허용. user 접근 시 403."""
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다")
    return user
