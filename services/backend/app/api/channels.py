import logging
from typing import Any

import httpx
import redis.asyncio as aioredis
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import delete as sa_delete, update as sa_update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.api.agent.instruction_agent import analyze_instruction
from app.config import config
from app.db.session import AsyncSessionLocal
from app.db.models import CctvChannel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/channels", tags=["channels"])

MEDIAMTX_API = "http://mediamtx:9997"

_store: dict[str, dict[str, Any]] = {}
_redis = aioredis.from_url(config.REDIS_URL, decode_responses=True)


class ChannelCreate(BaseModel):
    slot:        int
    name:        str
    channelName: str
    rtspUrl:     str | None = None
    sourceType:  str
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


async def _mediamtx_add_empty(channel_name: str) -> None:
    """source 없이 path만 등록 — 브라우저 WHIP push 허용용"""
    async with httpx.AsyncClient() as client:
        res = await client.post(
            f"{MEDIAMTX_API}/v3/config/paths/add/{channel_name}",
            json={},
        )
        logger.info("mediamtx add empty path %s → %d", channel_name, res.status_code)
        if res.status_code == 400 and "already exists" in res.text:
            return  # 이미 존재하면 OK


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

    cam_id = f"cam{body.slot}"

    if body.sourceType == "rtsp":
        if not body.rtspUrl:
            raise HTTPException(status_code=400, detail="RTSP 소스는 rtspUrl이 필수입니다.")
        await _mediamtx_add(body.channelName, body.rtspUrl)
        # ingestion은 mediamtx 재스트림으로 연결 (카메라 이중 접속 방지)
        ingestion_url  = f"rtsp://mediamtx:8554/{body.channelName}"
        ingestion_type = "rtsp"

    elif body.sourceType == "webcam":
        # MediaMTX에 path 사전 등록 (source 없음) → 브라우저 WHIP push 허용
        await _mediamtx_add_empty(body.channelName)
        ingestion_url  = f"rtsp://mediamtx:8554/{body.channelName}"
        ingestion_type = "rtsp"

    elif body.sourceType == "file":
        filename = (body.rtspUrl or "").lstrip("/").removeprefix("sample/")
        ingestion_url  = f"/sample/{filename}"
        ingestion_type = "file"

    else:
        ingestion_url  = body.rtspUrl or ""
        ingestion_type = body.sourceType

    await _redis.set(f"camera:{cam_id}:source_url", ingestion_url)
    await _redis.set(f"camera:{cam_id}:source_type", ingestion_type)
    if body.description:
        await _redis.set(f"camera_instruction:{cam_id}", body.description)
    else:
        await _redis.delete(f"camera_instruction:{cam_id}")

    async with AsyncSessionLocal() as session:
        async with session.begin():
            stmt = pg_insert(CctvChannel).values(
                camera_id=cam_id,
                camera_name=body.channelName,
                source_type=ingestion_type,
                source_url=ingestion_url,
                description=body.description or None,
            ).on_conflict_do_update(
                index_elements=["camera_id"],
                set_={
                    "camera_name": body.channelName,
                    "source_type": ingestion_type,
                    "source_url": ingestion_url,
                    "description": body.description or None,
                },
            )
            await session.execute(stmt)

    channel = {**body.model_dump(), "ingestion_url": ingestion_url}
    _store[body.channelName] = channel
    logger.info("채널 등록: cam_id=%s ingestion_url=%s", cam_id, ingestion_url)
    return channel


@router.put("/{channel_name}")
async def update_channel(channel_name: str, body: ChannelUpdate) -> dict:
    if channel_name not in _store:
        raise HTTPException(status_code=404, detail="채널을 찾을 수 없습니다.")

    channel = _store[channel_name]

    if body.rtspUrl and body.rtspUrl != channel.get("rtspUrl"):
        await _mediamtx_delete(channel_name)
        await _mediamtx_add(channel_name, body.rtspUrl)

    if body.name        is not None: channel["name"]        = body.name
    if body.rtspUrl     is not None: channel["rtspUrl"]     = body.rtspUrl
    if body.description is not None: channel["description"] = body.description
    if body.options     is not None: channel["options"]     = body.options

    if body.description is not None:
        slot = channel.get("slot")
        if slot is not None:
            cam_id = f"cam{slot}"
            if body.description:
                await _redis.set(f"camera_instruction:{cam_id}", body.description)
            else:
                await _redis.delete(f"camera_instruction:{cam_id}")
            async with AsyncSessionLocal() as session:
                async with session.begin():
                    await session.execute(
                        sa_update(CctvChannel)
                        .where(CctvChannel.camera_id == cam_id)
                        .values(description=body.description or None)
                    )

    return channel


@router.delete("/{channel_name}", status_code=204)
async def delete_channel(channel_name: str) -> None:
    if channel_name not in _store:
        raise HTTPException(status_code=404, detail="채널을 찾을 수 없습니다.")

    await _mediamtx_delete(channel_name)

    slot = _store[channel_name].get("slot")
    if slot is not None:
        cam_id = f"cam{slot}"
        await _redis.delete(
            f"camera:{cam_id}:source_url",
            f"camera:{cam_id}:source_type",
            f"camera_instruction:{cam_id}",
        )
        async with AsyncSessionLocal() as session:
            async with session.begin():
                # EventLog는 의도적으로 남겨둠 — 채널 삭제 후에도 검색/snapshot 접근 가능
                await session.execute(
                    sa_delete(CctvChannel).where(CctvChannel.camera_id == cam_id)
                )

    _store.pop(channel_name)


class InstructionAnalyzeRequest(BaseModel):
    text: str


class InstructionConfirmRequest(BaseModel):
    static: list[str]
    dynamic: list[str]


@router.post("/{camera_id}/instruction/analyze")
async def analyze_channel_instruction(camera_id: str, body: InstructionAnalyzeRequest) -> dict:
    """채널별 자유 텍스트를 에이전트로 분석해 static/dynamic 초안 반환."""
    try:
        result = await analyze_instruction(body.text)
    except Exception as e:
        logger.error("채널 instruction 분석 실패 camera_id=%s: %s", camera_id, e)
        raise HTTPException(status_code=500, detail="분석에 실패했습니다. 다시 시도해주세요.")
    return {
        "camera_id": camera_id,
        "static": result.get("static", []),
        "dynamic": result.get("dynamic", []),
    }


@router.patch("/{camera_id}/instruction/confirm")
async def confirm_channel_instruction(camera_id: str, body: InstructionConfirmRequest) -> dict:
    """확정된 채널별 체크리스트를 Redis camera_instruction:{camera_id}에 저장.

    inference의 render_prompt()가 이 키를 읽어 VLM 프롬프트에 주입한다.
    """
    static_part = "\n".join(f"- {item}" for item in body.static) if body.static else ""
    dynamic_part = "\n".join(f"- {item}" for item in body.dynamic) if body.dynamic else ""

    parts = []
    if static_part:
        parts.append(f"[Static 추가]\n{static_part}")
    if dynamic_part:
        parts.append(f"[Dynamic 추가]\n{dynamic_part}")

    instruction_value = "\n\n".join(parts)
    await _redis.set(f"camera_instruction:{camera_id}", instruction_value)

    logger.info("채널 instruction 저장: camera_id=%s static=%d dynamic=%d",
                camera_id, len(body.static), len(body.dynamic))
    return {"camera_id": camera_id, "status": "saved"}
