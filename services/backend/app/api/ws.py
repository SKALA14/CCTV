# services/backend/app/api/ws.py
import asyncio
import json
import logging
import uuid

import redis.asyncio as aioredis
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.api.auth import _decode_token
from app.config import config
from app.db.session import AsyncSessionLocal
from app.db.models import User

router = APIRouter()
logger = logging.getLogger(__name__)


@router.websocket("/ws")
async def ws_events(websocket: WebSocket):
    # httpOnly 쿠키에서 JWT 검증 — nginx same-origin 프록시 덕분에 쿠키 자동 전송됨
    token = websocket.cookies.get("access_token")
    if not token:
        await websocket.close(code=4001)  # 4001: 미인증
        logger.warning("[ws] 쿠키 없음 — 연결 거부")
        return
    try:
        payload = _decode_token(token)
    except Exception:
        await websocket.close(code=4001)
        logger.warning("[ws] 토큰 유효하지 않음 — 연결 거부")
        return

    # DB에서 User 조회 — role/site_id 기반 현장 격리에 사용
    try:
        async with AsyncSessionLocal() as session:
            user = await session.get(User, uuid.UUID(payload["sub"]))
    except Exception:
        await websocket.close(code=4001)
        logger.warning("[ws] User DB 조회 실패 — 연결 거부")
        return

    if user is None:
        await websocket.close(code=4001)
        logger.warning("[ws] 존재하지 않는 사용자 — 연결 거부")
        return

    ws_site_id    = user.site_id   # UUID | None
    is_superadmin = user.role == "superadmin"

    await websocket.accept()
    r = aioredis.from_url(config.REDIS_URL, decode_responses=True)

    last_ids = {
        config.ALERTS_STREAM: "$",
        config.EVENTS_STREAM: "$",
    }

    try:
        while True:
            try:
                results = await r.xread(last_ids, count=10, block=1000)
            except asyncio.CancelledError:
                break

            for stream, messages in results:
                for msg_id, fields in messages:
                    last_ids[stream] = msg_id

                    # 현장 격리: non-superadmin은 자기 현장 메시지만 수신
                    if not is_superadmin:
                        msg_site_id_str = fields.get("site_id")
                        if not msg_site_id_str:
                            continue  # site_id 없는 메시지는 non-superadmin에게 skip
                        try:
                            if uuid.UUID(msg_site_id_str) != ws_site_id:
                                continue
                        except (ValueError, AttributeError):
                            continue

                    await websocket.send_text(json.dumps({
                        "type": "new_event",
                        "payload": {
                            "channel_id":   fields.get("camera_id"),
                            "event_type":   fields.get("anomaly_type"),
                            "danger_level": fields.get("danger_level"),
                            "reason":       fields.get("description"),
                            "pipeline":     "emergency" if stream == config.ALERTS_STREAM else "general",
                            "timestamp":    fields.get("timestamp"),
                        },
                    }, ensure_ascii=False))

    except WebSocketDisconnect:
        logger.info("WebSocket 클라이언트 연결 종료")
    finally:
        await r.aclose()
