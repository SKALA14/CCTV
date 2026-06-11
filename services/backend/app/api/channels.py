import json
import logging
import uuid
from pathlib import Path
from typing import Any

import httpx
import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import delete as sa_delete, update as sa_update, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.api.deps import get_current_user, require_admin
from app.api.agent.instruction_agent import analyze_instruction
from app.config import config
from app.db.session import AsyncSessionLocal
from app.db.models import CctvChannel, User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/channels", tags=["channels"])

MEDIAMTX_API = "http://mediamtx:9997"

_store: dict[str, dict[str, Any]] = {}
_redis = aioredis.from_url(config.REDIS_URL, decode_responses=True)


def _store_key(site_id: str, channel_name: str) -> str:
    return f"{site_id}:{channel_name}"


def _redis_cam_prefix(site_id: str, cam_id: str) -> str:
    return f"camera:{site_id}:{cam_id}"


def _mediamtx_channel_name(site_id: str, channel_name: str) -> str:
    """mediamtx path: 현장 간 충돌 방지를 위해 site_id 앞 8자를 prefix로 사용."""
    return f"{str(site_id)[:8]}_{channel_name}"


def _get_zone_note(zone_name: str, site_id: str) -> str:
    """현장별 zones.json에서 해당 구역의 비고 반환. 없으면 빈 문자열."""
    zones_path = Path(config.PROMPTS_DIR) / str(site_id) / "zones.json"
    if not zones_path.exists():
        return ""
    try:
        data = json.loads(zones_path.read_text(encoding="utf-8"))
        for z in data:
            if isinstance(z, dict) and z.get("zone") == zone_name:
                return z.get("note", "")
    except Exception:
        pass
    return ""


class ChannelCreate(BaseModel):
    slot:        int
    name:        str
    channelName: str
    rtspUrl:     str | None = None
    sourceType:  str
    description: str = ""
    options:     list[str] = []
    zone:        str = ""


class ChannelUpdate(BaseModel):
    name:        str | None = None
    rtspUrl:     str | None = None
    description: str | None = None
    options:     list[str] | None = None
    zone:        str | None = None


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
    # MediaMTX v3 경로 삭제는 /v3/config/paths/delete/{name} (구 /remove/ 아님)
    async with httpx.AsyncClient() as client:
        res = await client.delete(
            f"{MEDIAMTX_API}/v3/config/paths/delete/{channel_name}",
        )
    if res.status_code not in (200, 204, 404):
        raise HTTPException(status_code=502, detail=f"mediamtx 삭제 실패: {res.text}")


@router.get("")
async def list_channels(
    site_id: str | None = Query(None),
    current_user: User = Depends(get_current_user),   # viewer 이상
) -> list[dict]:
    # 자기 현장 채널만 (admin/user 2단계 — 교차 현장 조회 없음)
    if current_user.site_id is None:
        raise HTTPException(status_code=403, detail="현장이 지정되지 않은 계정입니다.")
    site_id_str = str(current_user.site_id)
    return [v for k, v in _store.items() if k.startswith(f"{site_id_str}:")]


@router.post("", status_code=201)
async def create_channel(
    body: ChannelCreate,
    current_user: User = Depends(require_admin),   # admin만 허용
) -> dict:
    if current_user.site_id is None:
        raise HTTPException(
            status_code=403,
            detail="현장이 지정되지 않은 계정입니다.",
        )

    site_id_str = str(current_user.site_id)
    store_key   = _store_key(site_id_str, body.channelName)

    if store_key in _store:
        raise HTTPException(status_code=409, detail="이미 등록된 channelName입니다.")

    cam_id     = f"cam{body.slot}"
    mtx_name   = _mediamtx_channel_name(site_id_str, body.channelName)
    cam_prefix = _redis_cam_prefix(site_id_str, cam_id)

    if body.sourceType == "rtsp":
        if not body.rtspUrl:
            raise HTTPException(status_code=400, detail="RTSP 소스는 rtspUrl이 필수입니다.")
        await _mediamtx_add(mtx_name, body.rtspUrl)
        # ingestion은 mediamtx 재스트림으로 연결 (카메라 이중 접속 방지)
        ingestion_url  = f"rtsp://mediamtx:8554/{mtx_name}"
        ingestion_type = "rtsp"

    elif body.sourceType == "webcam":
        # MediaMTX에 path 사전 등록 (source 없음) → 브라우저 WHIP push 허용
        await _mediamtx_add_empty(mtx_name)
        ingestion_url  = f"rtsp://mediamtx:8554/{mtx_name}"
        ingestion_type = "rtsp"

    elif body.sourceType == "file":
        filename = (body.rtspUrl or "").lstrip("/").removeprefix("sample/")
        ingestion_url  = f"/sample/{filename}"
        ingestion_type = "file"

    else:
        ingestion_url  = body.rtspUrl or ""
        ingestion_type = body.sourceType

    await _redis.set(f"{cam_prefix}:source_url", ingestion_url)
    await _redis.set(f"{cam_prefix}:source_type", ingestion_type)
    if body.zone:
        await _redis.set(f"{cam_prefix}:zone", body.zone)
        note = _get_zone_note(body.zone, site_id_str)
        if note:
            await _redis.set(f"camera_instruction:{site_id_str}:{cam_id}", note)
        else:
            await _redis.delete(f"camera_instruction:{site_id_str}:{cam_id}")
    else:
        await _redis.delete(f"{cam_prefix}:zone")
        await _redis.delete(f"camera_instruction:{site_id_str}:{cam_id}")

    async with AsyncSessionLocal() as session:
        async with session.begin():
            stmt = pg_insert(CctvChannel).values(
                site_id=current_user.site_id,
                camera_id=cam_id,
                camera_name=body.channelName,
                source_type=ingestion_type,
                source_url=ingestion_url,
                description=body.description or None,
            ).on_conflict_do_update(
                constraint="uq_channel_per_site",
                set_={
                    "camera_name": body.channelName,
                    "source_type": ingestion_type,
                    "source_url": ingestion_url,
                    "description": body.description or None,
                },
            )
            await session.execute(stmt)

    channel = {**body.model_dump(), "ingestion_url": ingestion_url, "mtxPath": mtx_name}
    _store[store_key] = channel
    logger.info("채널 등록: site_id=%s cam_id=%s ingestion_url=%s", site_id_str, cam_id, ingestion_url)

    # static 프로세스에 즉시 스캔 트리거
    await _redis.publish("camera:registered", f"{site_id_str}:{cam_id}")

    return channel


@router.put("/{channel_name}")
async def update_channel(
    channel_name: str,
    body: ChannelUpdate,
    current_user: User = Depends(require_admin),   # admin만 허용
) -> dict:
    if current_user.site_id is None:
        raise HTTPException(
            status_code=403,
            detail="현장이 지정되지 않은 계정입니다.",
        )

    site_id_str = str(current_user.site_id)
    store_key   = _store_key(site_id_str, channel_name)

    if store_key not in _store:
        raise HTTPException(status_code=404, detail="채널을 찾을 수 없습니다.")

    channel = _store[store_key]
    slot = channel.get("slot")
    cam_id = f"cam{slot}" if slot is not None else None
    mtx_name   = _mediamtx_channel_name(site_id_str, channel_name)
    cam_prefix = _redis_cam_prefix(site_id_str, cam_id) if cam_id else None

    new_ingestion_url: str | None = None
    if body.rtspUrl is not None and body.rtspUrl != channel.get("rtspUrl"):
        source_type = channel.get("sourceType", "")
        if source_type in ("rtsp", "webcam"):
            await _mediamtx_delete(mtx_name)
            await _mediamtx_add(mtx_name, body.rtspUrl)
            # ingestion_url은 rtsp://mediamtx:8554/{mtx_name}으로 고정 — 변경 불필요
        elif source_type == "file":
            filename = body.rtspUrl.lstrip("/").removeprefix("sample/")
            new_ingestion_url = f"/sample/{filename}"
            channel["ingestion_url"] = new_ingestion_url
            if cam_prefix:
                await _redis.set(f"{cam_prefix}:source_url", new_ingestion_url)
                await _redis.publish("camera:registered", f"{site_id_str}:{cam_id}")

    if body.name        is not None: channel["name"]        = body.name
    if body.rtspUrl     is not None: channel["rtspUrl"]     = body.rtspUrl
    if body.description is not None: channel["description"] = body.description
    if body.options     is not None: channel["options"]     = body.options
    if body.zone        is not None: channel["zone"]        = body.zone

    if cam_id and cam_prefix:
        db_values: dict = {}
        if new_ingestion_url is not None:
            db_values["source_url"] = new_ingestion_url
        if body.description is not None:
            db_values["description"] = body.description or None
        if body.zone is not None:
            if body.zone:
                await _redis.set(f"{cam_prefix}:zone", body.zone)
                note = _get_zone_note(body.zone, site_id_str)
                if note:
                    await _redis.set(f"camera_instruction:{site_id_str}:{cam_id}", note)
                else:
                    await _redis.delete(f"camera_instruction:{site_id_str}:{cam_id}")
            else:
                await _redis.delete(f"{cam_prefix}:zone")
                await _redis.delete(f"camera_instruction:{site_id_str}:{cam_id}")
        if db_values:
            async with AsyncSessionLocal() as session:
                async with session.begin():
                    await session.execute(
                        sa_update(CctvChannel)
                        .where(CctvChannel.camera_id == cam_id)
                        .where(CctvChannel.site_id == current_user.site_id)
                        .values(**db_values)
                    )

    return channel


@router.delete("/{channel_name}", status_code=204)
async def delete_channel(
    channel_name: str,
    current_user: User = Depends(require_admin),   # admin만 허용
) -> None:
    if current_user.site_id is None:
        raise HTTPException(
            status_code=403,
            detail="현장이 지정되지 않은 계정입니다.",
        )

    site_id_str = str(current_user.site_id)
    store_key   = _store_key(site_id_str, channel_name)

    if store_key not in _store:
        raise HTTPException(status_code=404, detail="채널을 찾을 수 없습니다.")

    mtx_name = _mediamtx_channel_name(site_id_str, channel_name)
    await _mediamtx_delete(mtx_name)

    slot = _store[store_key].get("slot")
    if slot is not None:
        cam_id     = f"cam{slot}"
        cam_prefix = _redis_cam_prefix(site_id_str, cam_id)
        await _redis.delete(
            f"{cam_prefix}:source_url",
            f"{cam_prefix}:source_type",
            f"{cam_prefix}:zone",
            f"camera_instruction:{site_id_str}:{cam_id}",
        )
        async with AsyncSessionLocal() as session:
            async with session.begin():
                # EventLog는 의도적으로 남겨둠 — 채널 삭제 후에도 검색/snapshot 접근 가능
                await session.execute(
                    sa_delete(CctvChannel)
                    .where(CctvChannel.camera_id == cam_id)
                    .where(CctvChannel.site_id == current_user.site_id)
                )

    _store.pop(store_key)


class InstructionAnalyzeRequest(BaseModel):
    text: str


class InstructionConfirmRequest(BaseModel):
    static: list[str]
    dynamic: list[str]


@router.post("/{camera_id}/instruction/analyze")
async def analyze_channel_instruction(camera_id: str, body: InstructionAnalyzeRequest, current_user: User = Depends(require_admin)) -> dict:
    """채널별 자유 텍스트를 에이전트로 분석해 static/dynamic 초안 반환."""
    if current_user.site_id is None:
        raise HTTPException(
            status_code=403,
            detail="현장이 지정되지 않은 계정입니다.",
        )
    try:
        result = await analyze_instruction(body.text, str(current_user.site_id))
    except Exception as e:
        logger.error("채널 instruction 분석 실패 camera_id=%s: %s", camera_id, e)
        raise HTTPException(status_code=500, detail="분석에 실패했습니다. 다시 시도해주세요.")
    return {
        "camera_id": camera_id,
        "static": result.get("static", []),
        "dynamic": result.get("dynamic", []),
    }


@router.patch("/{camera_id}/instruction/confirm")
async def confirm_channel_instruction(camera_id: str, body: InstructionConfirmRequest, current_user: User = Depends(require_admin)) -> dict:
    """확정된 채널별 체크리스트를 Redis camera_instruction:{site_id}:{camera_id}에 저장.

    inference의 render_prompt()가 이 키를 읽어 VLM 프롬프트에 주입한다.
    """
    if current_user.site_id is None:
        raise HTTPException(
            status_code=403,
            detail="현장이 지정되지 않은 계정입니다.",
        )

    site_id_str = str(current_user.site_id)
    static_part = "\n".join(f"- {item}" for item in body.static) if body.static else ""
    dynamic_part = "\n".join(f"- {item}" for item in body.dynamic) if body.dynamic else ""

    parts = []
    if static_part:
        parts.append(f"[Static 추가]\n{static_part}")
    if dynamic_part:
        parts.append(f"[Dynamic 추가]\n{dynamic_part}")

    instruction_value = "\n\n".join(parts)
    await _redis.set(f"camera_instruction:{site_id_str}:{camera_id}", instruction_value)

    logger.info("채널 instruction 저장: site_id=%s camera_id=%s static=%d dynamic=%d",
                site_id_str, camera_id, len(body.static), len(body.dynamic))
    return {"camera_id": camera_id, "status": "saved"}
