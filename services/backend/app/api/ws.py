import asyncio
import json
import logging

import redis.asyncio as aioredis
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.config import config

router = APIRouter()
logger = logging.getLogger(__name__)


@router.websocket("/ws")
async def ws_events(websocket: WebSocket):
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