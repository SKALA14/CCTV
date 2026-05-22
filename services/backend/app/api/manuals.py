import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

import redis.asyncio as aioredis
from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from app.api.agent.checklist_agent import analyze_pdf, refine_checklist
from app.api.agent.pdf_parser import extract_text_from_pdf
from app.config import config

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/manuals", tags=["manuals"])

_MANUALS_KEY = "manuals:list"
_STATIC_FILE = "static_checklist.md"
_DYNAMIC_FILE = "dynamic_checklist.md"
_redis: aioredis.Redis | None = None


def _get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(config.REDIS_URL, decode_responses=True)
    return _redis


class RefineRequest(BaseModel):
    session_id: str
    feedback: str


class ConfirmRequest(BaseModel):
    session_id: str
    static: list[str]
    dynamic: list[str]


@router.get("")
async def list_manuals() -> list[dict]:
    """업로드된 매뉴얼 파일 메타데이터 목록."""
    raw = await _get_redis().get(_MANUALS_KEY)
    return json.loads(raw) if raw else []


@router.post("")
async def upload_manual(file: UploadFile = File(...)) -> dict:
    """매뉴얼 파일 메타데이터를 Redis에 저장."""
    meta = {
        "id": str(uuid.uuid4()),
        "name": file.filename or "unknown",
        "size": 0,
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
        "type": file.content_type or "",
    }
    content = await file.read()
    meta["size"] = len(content)

    r = _get_redis()
    raw = await r.get(_MANUALS_KEY)
    files: list[dict] = json.loads(raw) if raw else []
    files.insert(0, meta)
    await r.set(_MANUALS_KEY, json.dumps(files, ensure_ascii=False))
    return meta


@router.delete("/{file_id}")
async def delete_manual(file_id: str) -> dict:
    """매뉴얼 파일 메타데이터를 Redis에서 삭제."""
    r = _get_redis()
    raw = await r.get(_MANUALS_KEY)
    files: list[dict] = json.loads(raw) if raw else []
    files = [f for f in files if f["id"] != file_id]
    await r.set(_MANUALS_KEY, json.dumps(files, ensure_ascii=False))
    return {"status": "deleted"}


@router.get("/checklist")
async def get_current_checklist() -> dict:
    """현재 적용 중인 글로벌 체크리스트 파일 내용 반환."""
    prompts_dir = Path(config.PROMPTS_DIR)
    static_path = prompts_dir / _STATIC_FILE
    dynamic_path = prompts_dir / _DYNAMIC_FILE
    return {
        "static": static_path.read_text(encoding="utf-8") if static_path.exists() else "",
        "dynamic": dynamic_path.read_text(encoding="utf-8") if dynamic_path.exists() else "",
    }


@router.post("/analyze")
async def analyze_manual(file: UploadFile = File(...)) -> dict:
    """PDF 업로드 → 3단계 에이전트 분석 → 체크리스트 초안과 session_id 반환."""
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="PDF 파일만 분석 가능합니다.")

    content = await file.read()
    try:
        pdf_text = extract_text_from_pdf(content)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    try:
        result, session_id = await analyze_pdf(pdf_text)
    except Exception as e:
        logger.error("에이전트 분석 실패: %s", e)
        raise HTTPException(status_code=500, detail="체크리스트 분석에 실패했습니다. 다시 시도해주세요.")

    return {"session_id": session_id, "static": result.get("static", []), "dynamic": result.get("dynamic", [])}


@router.post("/refine")
async def refine_manual(body: RefineRequest) -> dict:
    """피드백 반영해 체크리스트 재생성."""
    try:
        result = await refine_checklist(body.session_id, body.feedback)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("체크리스트 재생성 실패: %s", e)
        raise HTTPException(status_code=500, detail="재생성에 실패했습니다. 이전 결과를 유지합니다.")

    return {"session_id": body.session_id, "static": result.get("static", []), "dynamic": result.get("dynamic", [])}


@router.post("/confirm")
async def confirm_manual(body: ConfirmRequest) -> dict:
    """확정된 체크리스트를 backend/prompts/{static,dynamic}_checklist.md에 저장.

    inference의 _load_checklist()가 같은 파일을 매 VLM 호출 시 읽음 — 즉시 반영.
    """
    prompts_dir = Path(config.PROMPTS_DIR)
    prompts_dir.mkdir(parents=True, exist_ok=True)

    static_body = "\n".join(f"- {item}" for item in body.static)
    dynamic_body = "\n".join(f"- {item}" for item in body.dynamic)

    (prompts_dir / _STATIC_FILE).write_text(static_body, encoding="utf-8")
    (prompts_dir / _DYNAMIC_FILE).write_text(dynamic_body, encoding="utf-8")

    logger.info("글로벌 체크리스트 저장 완료: static=%d items, dynamic=%d items",
                len(body.static), len(body.dynamic))
    return {"status": "saved", "static_count": len(body.static), "dynamic_count": len(body.dynamic)}
