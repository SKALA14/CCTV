import csv
import io
import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

import redis.asyncio as aioredis
from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from app.api.agent.checklist_agent import analyze_pdf, refine_checklist, subset_by_zones
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


class ZoneChecklist(BaseModel):
    zone: str
    static: list[str]
    dynamic: list[str]


class ConfirmRequest(BaseModel):
    session_id: str
    static: list[str]
    dynamic: list[str]
    zones: list[ZoneChecklist] = []


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
    """PDF 업로드 → 체크리스트 분석. zones.json이 있으면 구역별 subset도 반환."""
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

    def _flatten(categories: list) -> list[str]:
        return [item for cat in categories for item in (cat.get("items", []) if isinstance(cat, dict) else [])]

    zone_results = []
    zones_path = Path(config.PROMPTS_DIR) / "zones.json"
    if zones_path.exists():
        try:
            raw_zones = json.loads(zones_path.read_text(encoding="utf-8"))
            if raw_zones:
                zones = [
                    {"zone": z["zone"], "description": z.get("description", "")}
                    if isinstance(z, dict) else {"zone": z, "description": ""}
                    for z in raw_zones
                ]
                zone_results = await subset_by_zones(result, zones)
        except Exception as e:
            logger.error("구역 subset 생성 실패: %s", e)

    return {
        "session_id": session_id,
        "static": _flatten(result.get("static", [])),
        "dynamic": _flatten(result.get("dynamic", [])),
        "zones": zone_results,
    }


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

    def _flatten(categories: list) -> list[str]:
        return [item for cat in categories for item in (cat.get("items", []) if isinstance(cat, dict) else [cat])]

    return {
        "session_id": body.session_id,
        "static": _flatten(result.get("static", [])),
        "dynamic": _flatten(result.get("dynamic", [])),
    }


def _parse_zones(content: bytes, filename: str) -> list[dict]:
    """CSV/XLSX에서 zone, description, 비고 컬럼 파싱."""
    if filename.lower().endswith(".xlsx"):
        import openpyxl
        wb = openpyxl.load_workbook(io.BytesIO(content))
        ws = wb.active
        rows = list(ws.iter_rows(values_only=True))
        if not rows:
            return []
        header = [str(c).strip().lower() if c else "" for c in rows[0]]
        zi = header.index("zone") if "zone" in header else 0
        di = header.index("description") if "description" in header else 1
        ni = next((i for i, h in enumerate(header) if h in ("비고", "note")), 2 if len(header) > 2 else None)
        return [
            {
                "zone": str(r[zi] or "").strip(),
                "description": str(r[di] or "").strip(),
                "note": str(r[ni] or "").strip() if ni is not None and ni < len(r) else "",
            }
            for r in rows[1:] if r and r[zi]
        ]
    text = content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    return [
        {
            "zone": row.get("zone", "").strip(),
            "description": row.get("description", "").strip(),
            "note": row.get("비고", row.get("note", "")).strip(),
        }
        for row in reader if row.get("zone", "").strip()
    ]



@router.post("/zones")
async def register_zones(zones_file: UploadFile = File(...)) -> dict:
    """구역 파일만 업로드해 zones.json 저장 + 비고를 Redis에 저장. LLM 호출 없음."""
    content = await zones_file.read()
    try:
        zones = _parse_zones(content, zones_file.filename or "")
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"구역 파일 파싱 실패: {e}")
    if not zones:
        raise HTTPException(status_code=422, detail="구역 정보가 없습니다. zone, description 컬럼을 확인하세요.")

    prompts_dir = Path(config.PROMPTS_DIR)
    prompts_dir.mkdir(parents=True, exist_ok=True)
    (prompts_dir / "zones.json").write_text(
        json.dumps(zones, ensure_ascii=False), encoding="utf-8"
    )

    return {"status": "saved", "zones": [z["zone"] for z in zones]}


@router.get("/zones")
async def list_zones() -> list[str]:
    """저장된 구역 이름 목록 반환."""
    prompts_dir = Path(config.PROMPTS_DIR)
    zones_file = prompts_dir / "zones.json"
    if not zones_file.exists():
        return []
    data = json.loads(zones_file.read_text(encoding="utf-8"))
    return [z["zone"] if isinstance(z, dict) else z for z in data]


@router.post("/confirm")
async def confirm_manual(body: ConfirmRequest) -> dict:
    """확정된 체크리스트를 backend/prompts/에 저장.

    - 글로벌: {static,dynamic}_checklist.md
    - 구역별: zone_{safe_name}_{static,dynamic}.md
    inference의 _load_checklist()가 같은 파일을 매 VLM 호출 시 읽음 — 즉시 반영.
    """
    prompts_dir = Path(config.PROMPTS_DIR)
    prompts_dir.mkdir(parents=True, exist_ok=True)

    (prompts_dir / _STATIC_FILE).write_text("\n".join(f"- {item}" for item in body.static), encoding="utf-8")
    (prompts_dir / _DYNAMIC_FILE).write_text("\n".join(f"- {item}" for item in body.dynamic), encoding="utf-8")

    for z in body.zones:
        safe = z.zone.replace(" ", "_")
        (prompts_dir / f"zone_{safe}_static.md").write_text(
            "\n".join(f"- {item}" for item in z.static), encoding="utf-8"
        )
        (prompts_dir / f"zone_{safe}_dynamic.md").write_text(
            "\n".join(f"- {item}" for item in z.dynamic), encoding="utf-8"
        )

    logger.info("체크리스트 저장 완료: static=%d, dynamic=%d, zones=%d",
                len(body.static), len(body.dynamic), len(body.zones))
    return {"status": "saved", "static_count": len(body.static), "dynamic_count": len(body.dynamic)}
