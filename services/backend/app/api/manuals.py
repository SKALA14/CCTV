import csv
import io
import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, Query
from pydantic import BaseModel

from app.api.deps import require_admin, get_current_user
from app.db.models import User
from app.api.agent.checklist_agent import analyze_pdf, refine_checklist, subset_by_zones, normalize_categories
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


def _site_dir(site_id) -> Path:
    """현장별 체크리스트/구역 저장 디렉토리. 없으면 생성."""
    d = Path(config.PROMPTS_DIR) / str(site_id)
    d.mkdir(parents=True, exist_ok=True)
    return d


def _effective_site_id(current_user, site_id_param: str | None):
    """현장 결정: superadmin은 쿼리 파라미터, 그 외는 자기 현장.

    superadmin이 파라미터 미지정/형식오류 시 None 반환(쓰기 차단 신호).
    """
    if current_user.role == "superadmin":
        if not site_id_param:
            return None
        try:
            return uuid.UUID(site_id_param)
        except (ValueError, AttributeError, TypeError):
            return None
    return current_user.site_id


class RefineRequest(BaseModel):
    session_id: str
    feedback: str


class CategoryItem(BaseModel):
    code: str
    label: str
    items: list[str]


class ZoneChecklist(BaseModel):
    zone: str
    static: list[str]
    dynamic: list[str]


class ConfirmRequest(BaseModel):
    session_id: str
    static: list[str]
    dynamic: list[str]
    static_categories: list[CategoryItem] = []   # 없으면 기존 형식 유지
    dynamic_categories: list[CategoryItem] = []  # 없으면 기존 형식 유지
    zones: list[ZoneChecklist] = []


def _format_checklist(items: list[str], categories: list) -> str:
    """번호 형식 체크리스트 텍스트 생성.

    categories 여부와 무관하게 항상 번호 형식 반환.
    코드 매핑은 _build_categories_map()이 별도 처리.
    """
    if not items:
        return ""
    return "\n".join(f"{i + 1}. {item}" for i, item in enumerate(items))


def _build_categories_map(items: list[str], categories: list) -> dict[str, str]:
    """항목 인덱스(1-based 문자열) → 카테고리 코드 매핑 dict 생성.

    Redis HSET mapping으로 바로 사용 가능.
    categories 없으면 {} 반환.
    categories에 없는 항목은 'GENERAL' 코드 부여.
    """
    if not items or not categories:
        return {}
    item_to_code: dict[str, str] = {}
    for cat in categories:
        for item in cat.items:
            item_to_code[item] = cat.code
    return {
        str(i + 1): item_to_code.get(item, "GENERAL")
        for i, item in enumerate(items)
    }


@router.get("")
async def list_manuals(
    site_id: str | None = Query(None),
    current_user: User = Depends(require_admin),   # admin/superadmin
) -> list[dict]:
    """업로드된 매뉴얼 파일 메타데이터 목록 (현장별)."""
    sid = _effective_site_id(current_user, site_id)
    if sid is None:
        return []
    raw = await _get_redis().get(f"{_MANUALS_KEY}:{sid}")
    return json.loads(raw) if raw else []


@router.post("")
async def upload_manual(
    file: UploadFile = File(...),
    site_id: str | None = Query(None),   # superadmin은 현장 지정 필수
    current_user: User = Depends(require_admin),
) -> dict:
    """매뉴얼 파일 메타데이터를 현장별 Redis에 저장."""
    sid = _effective_site_id(current_user, site_id)
    if sid is None:
        raise HTTPException(status_code=403, detail="현장을 지정해야 합니다 (superadmin은 site_id 필요).")
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
    key = f"{_MANUALS_KEY}:{sid}"
    raw = await r.get(key)
    files: list[dict] = json.loads(raw) if raw else []
    files.insert(0, meta)
    await r.set(key, json.dumps(files, ensure_ascii=False))
    return meta


@router.delete("/{file_id}")
async def delete_manual(
    file_id: str,
    site_id: str | None = Query(None),
    current_user: User = Depends(require_admin),
) -> dict:
    sid = _effective_site_id(current_user, site_id)
    if sid is None:
        raise HTTPException(status_code=403, detail="현장을 지정해야 합니다 (superadmin은 site_id 필요).")
    r = _get_redis()
    key = f"{_MANUALS_KEY}:{sid}"
    raw = await r.get(key)
    files: list[dict] = json.loads(raw) if raw else []
    files = [f for f in files if f["id"] != file_id]
    await r.set(key, json.dumps(files, ensure_ascii=False))
    return {"status": "deleted"}


@router.get("/checklist")
async def get_current_checklist(
    site_id: str | None = Query(None),
    current_user: User = Depends(get_current_user),   # viewer 이상
) -> dict:
    """현재 적용 중인 현장 체크리스트 파일 내용 반환 (읽기 전용)."""
    sid = _effective_site_id(current_user, site_id)
    if sid is None:
        return {"static": "", "dynamic": ""}
    site_dir = _site_dir(sid)
    static_path = site_dir / _STATIC_FILE
    dynamic_path = site_dir / _DYNAMIC_FILE
    return {
        "static": static_path.read_text(encoding="utf-8") if static_path.exists() else "",
        "dynamic": dynamic_path.read_text(encoding="utf-8") if dynamic_path.exists() else "",
    }


@router.post("/analyze")
async def analyze_manual(
    file: UploadFile = File(...),
    site_id: str | None = Query(None),
    current_user: User = Depends(require_admin),
) -> dict:
    """PDF 업로드 → 체크리스트 분석. zones.json이 있으면 구역별 subset도 반환."""
    sid = _effective_site_id(current_user, site_id)
    if sid is None:
        raise HTTPException(status_code=403, detail="현장을 지정해야 합니다 (superadmin은 site_id 필요).")
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

    def _flatten(section: list) -> list[str]:
        """analyze_pdf 결과의 카테고리 구조에서 항목 문자열만 추출."""
        items: list[str] = []
        for entry in section:
            if isinstance(entry, dict):
                items.extend(entry.get("items", []))
            elif isinstance(entry, str):
                items.append(entry)
        return items

    static_items = _flatten(result.get("static", []))
    dynamic_items = _flatten(result.get("dynamic", []))

    # 카테고리 정규화 (실패해도 기존 items는 정상 반환)
    try:
        static_categories = await normalize_categories(static_items)
        dynamic_categories = await normalize_categories(dynamic_items)
    except Exception as e:
        logger.warning("카테고리 정규화 실패, 빈 배열로 대체: %s", e)
        static_categories = []
        dynamic_categories = []

    zone_results = []
    zones_path = _site_dir(sid) / "zones.json"
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
        "static": static_items,
        "dynamic": dynamic_items,
        "static_categories": static_categories,
        "dynamic_categories": dynamic_categories,
        "zones": zone_results,
    }


@router.post("/refine")
async def refine_manual(
    body: RefineRequest,
    site_id: str | None = Query(None),
    current_user: User = Depends(require_admin),
) -> dict:
    """피드백 반영해 체크리스트 재생성."""
    # refine은 세션 기반이라 sid를 직접 쓰진 않지만, 현장 미지정(권한 가드) 차단용
    sid = _effective_site_id(current_user, site_id)
    if sid is None:
        raise HTTPException(status_code=403, detail="현장을 지정해야 합니다 (superadmin은 site_id 필요).")
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
async def register_zones(
    zones_file: UploadFile = File(...),
    site_id: str | None = Query(None),
    current_user: User = Depends(require_admin),
) -> dict:
    sid = _effective_site_id(current_user, site_id)
    if sid is None:
        raise HTTPException(status_code=403, detail="현장을 지정해야 합니다 (superadmin은 site_id 필요).")
    content = await zones_file.read()
    try:
        zones = _parse_zones(content, zones_file.filename or "")
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"구역 파일 파싱 실패: {e}")
    if not zones:
        raise HTTPException(status_code=422, detail="구역 정보가 없습니다. zone, description 컬럼을 확인하세요.")
    site_dir = _site_dir(sid)
    (site_dir / "zones.json").write_text(
        json.dumps(zones, ensure_ascii=False), encoding="utf-8"
    )
    return {"status": "saved", "zones": [z["zone"] for z in zones]}


@router.get("/zones")
async def list_zones(
    site_id: str | None = Query(None),
    current_user: User = Depends(get_current_user),   # viewer 이상
) -> list[str]:
    """저장된 구역 이름 목록 반환 (현장별, 읽기 전용)."""
    sid = _effective_site_id(current_user, site_id)
    if sid is None:
        return []
    zones_file = _site_dir(sid) / "zones.json"
    if not zones_file.exists():
        return []
    data = json.loads(zones_file.read_text(encoding="utf-8"))
    return [z["zone"] if isinstance(z, dict) else z for z in data]


@router.post("/confirm")
async def confirm_manual(
    body: ConfirmRequest,
    site_id: str | None = Query(None),
    current_user: User = Depends(require_admin),
) -> dict:
    """확정된 체크리스트를 현장별 디렉토리/Redis에 저장."""
    sid = _effective_site_id(current_user, site_id)
    if sid is None:
        raise HTTPException(status_code=403, detail="현장을 지정해야 합니다 (superadmin은 site_id 필요).")
    site_dir = _site_dir(sid)
    redis = _get_redis()

    (site_dir / _STATIC_FILE).write_text(
        _format_checklist(body.static, body.static_categories), encoding="utf-8"
    )
    (site_dir / _DYNAMIC_FILE).write_text(
        _format_checklist(body.dynamic, body.dynamic_categories), encoding="utf-8"
    )

    static_map = _build_categories_map(body.static, body.static_categories)
    dynamic_map = _build_categories_map(body.dynamic, body.dynamic_categories)
    await redis.delete(f"checklist:{sid}:static:categories")
    if static_map:
        await redis.hset(f"checklist:{sid}:static:categories", mapping=static_map)
    await redis.delete(f"checklist:{sid}:dynamic:categories")
    if dynamic_map:
        await redis.hset(f"checklist:{sid}:dynamic:categories", mapping=dynamic_map)

    for z in body.zones:
        safe = z.zone.replace(" ", "_")
        static_cats = [c for c in body.static_categories if any(item in z.static for item in c.items)]
        dynamic_cats = [c for c in body.dynamic_categories if any(item in z.dynamic for item in c.items)]

        (site_dir / f"zone_{safe}_static.md").write_text(
            _format_checklist(z.static, static_cats), encoding="utf-8"
        )
        (site_dir / f"zone_{safe}_dynamic.md").write_text(
            _format_checklist(z.dynamic, dynamic_cats), encoding="utf-8"
        )

        zone_static_map = _build_categories_map(z.static, static_cats)
        zone_dynamic_map = _build_categories_map(z.dynamic, dynamic_cats)
        await redis.delete(f"checklist:{sid}:zone_{safe}:static:categories")
        if zone_static_map:
            await redis.hset(f"checklist:{sid}:zone_{safe}:static:categories", mapping=zone_static_map)
        await redis.delete(f"checklist:{sid}:zone_{safe}:dynamic:categories")
        if zone_dynamic_map:
            await redis.hset(f"checklist:{sid}:zone_{safe}:dynamic:categories", mapping=zone_dynamic_map)

    logger.info("체크리스트 저장 완료: site=%s static=%d dynamic=%d zones=%d",
                sid, len(body.static), len(body.dynamic), len(body.zones))
    return {"status": "saved", "static_count": len(body.static), "dynamic_count": len(body.dynamic)}
