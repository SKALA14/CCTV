import logging
from typing import Any

import httpx
import redis.asyncio as aioredis
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.config import config

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/channels", tags=["channels"])

MEDIAMTX_API = "http://mediamtx:9997"

_store: dict[str, dict[str, Any]] = {}
_redis = aioredis.from_url(config.REDIS_URL, decode_responses=True)


class ChannelCreate(BaseModel):
    slot:        int
    name:        str
    channelName: str
    rtspUrl:     str
    description: str = ""
    options:     list[str] = []


class ChannelUpdate(BaseModel):
    name:        str | None = None
    rtspUrl:     str | None = None
    description: str | None = None
    options:     list[str] | None = None


async def _mediamtx_add(channel_name: str, rtsp_url: str) -> None:
    async with httpx.AsyncClient() as client:
        res = await client.post(
            f"{MEDIAMTX_API}/v3/config/paths/add/{channel_name}",
            json={"source": rtsp_url},
        )
        logger.warning("mediamtx add %s → %d %s", channel_name, res.status_code, res.text)
        if res.status_code == 400 and "already exists" in res.text:
            res = await client.patch(
                f"{MEDIAMTX_API}/v3/config/paths/patch/{channel_name}",
                json={"source": rtsp_url},
            )
            logger.warning("mediamtx patch %s → %d %s", channel_name, res.status_code, res.text)
    if res.status_code not in (200, 201):
        raise HTTPException(status_code=502, detail=f"mediamtx 등록 실패: {res.text}")


async def _mediamtx_delete(channel_name: str) -> None:
    async with httpx.AsyncClient() as client:
        res = await client.delete(
            f"{MEDIAMTX_API}/v3/config/paths/remove/{channel_name}",
        )
    if res.status_code not in (200, 204, 404):
        raise HTTPException(status_code=502, detail=f"mediamtx 삭제 실패: {res.text}")


@router.get("")
async def list_channels() -> list[dict]:
    return list(_store.values())


@router.post("", status_code=201)
async def create_channel(body: ChannelCreate) -> dict:
    if body.channelName in _store:
        raise HTTPException(status_code=409, detail="이미 등록된 channelName입니다.")

    await _mediamtx_add(body.channelName, body.rtspUrl)

    cam_id = f"cam{body.slot}"
    await _redis.set(f"camera:{cam_id}:source_url", body.rtspUrl)
    await _redis.set(f"camera:{cam_id}:source_type", "rtsp")
    logger.info("ingestion source set: cam_id=%s url=%s", cam_id, body.rtspUrl)

    channel = body.model_dump()
    _store[body.channelName] = channel
    return channel


@router.put("/{channel_name}")
async def update_channel(channel_name: str, body: ChannelUpdate) -> dict:
    if channel_name not in _store:
        raise HTTPException(status_code=404, detail="채널을 찾을 수 없습니다.")

    channel = _store[channel_name]

    if body.rtspUrl and body.rtspUrl != channel["rtspUrl"]:
        await _mediamtx_delete(channel_name)
        await _mediamtx_add(channel_name, body.rtspUrl)

    if body.name        is not None: channel["name"]        = body.name
    if body.rtspUrl     is not None: channel["rtspUrl"]     = body.rtspUrl
    if body.description is not None: channel["description"] = body.description
    if body.options     is not None: channel["options"]     = body.options

    return channel


@router.delete("/{channel_name}", status_code=204)
async def delete_channel(channel_name: str) -> None:
    if channel_name not in _store:
        raise HTTPException(status_code=404, detail="채널을 찾을 수 없습니다.")

    await _mediamtx_delete(channel_name)

    slot = _store[channel_name].get("slot")
    if slot is not None:
        cam_id = f"cam{slot}"
        await _redis.delete(f"camera:{cam_id}:source_url", f"camera:{cam_id}:source_type")

    _store.pop(channel_name)
