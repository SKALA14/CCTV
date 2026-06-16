# services/backend/app/api/manuals.py
"""안전 매뉴얼 업로드·체크리스트 API. PDF 분석·구역 등록·확정/병합을 LLM 에이전트로 처리한다."""

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
from app.api import checklist_store
from app.db.models import User
from app.api.agent.checklist_agent import analyze_pdf, refine_checklist, subset_by_zones, normalize_categories, diff_checklist
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
    """현장 결정: 모든 계정은 자기 현장 (admin/user 2단계).

    site_id_param은 하위호환을 위해 남기되 무시한다(교차 현장 관리 없음).
    """
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


class MergeRequest(BaseModel):
    static_add: list[str] = []
    static_remove: list[str] = []
    dynamic_add: list[str] = []
    dynamic_remove: list[str] = []


def _cat_to_dict(cat) -> dict:
    """pydantic CategoryItem 또는 dict → dict 정규화."""
    if isinstance(cat, dict):
        return {"code": cat.get("code", "GENERAL"), "label": cat.get("label", ""), "items": list(cat.get("items", []))}
    return {"code": cat.code, "label": getattr(cat, "label", ""), "items": list(cat.items)}


def _format_checklist(items: list[str], categories: list) -> str:
    """번호 형식 체크리스트 텍스트. (store.format_numbered 위임, 기존 시그니처 유지)"""
    return checklist_store.format_numbered(items)


def _build_categories_map(items: list[str], categories: list) -> dict[str, str]:
    """항목 인덱스(1-based str) → 카테고리 코드. (기존 시그니처 유지)"""
    if not items or not categories:
        return {}
    lookup = checklist_store.item_to_code([_cat_to_dict(c) for c in categories])
    return {str(i + 1): lookup.get(item, "GENERAL") for i, item in enumerate(items)}


@router.get("")
async def list_manuals(
    site_id: str | None = Query(None),
    current_user: User = Depends(get_current_user),   # viewer 이상 — 읽기 전용 파일명 조회
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
    site_id: str | None = Query(None),   # 하위호환용 — 무시됨(자기 현장 사용)
    current_user: User = Depends(require_admin),
) -> dict:
    """매뉴얼 파일 메타데이터를 현장별 Redis에 저장."""
    sid = _effective_site_id(current_user, site_id)
    if sid is None:
        raise HTTPException(status_code=403, detail="현장이 지정되지 않은 계정입니다.")
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
        raise HTTPException(status_code=403, detail="현장이 지정되지 않은 계정입니다.")
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
    """현재 적용 중인 현장 체크리스트 반환 (읽기 전용). 공통 텍스트 + 구역별 항목."""
    sid = _effective_site_id(current_user, site_id)
    if sid is None:
        return {"static": "", "dynamic": "", "zones": []}
    site_dir = _site_dir(sid)
    structured = await checklist_store.load_structured(site_dir, _get_redis(), str(sid))
    zones = [
        {"zone": z.get("zone", ""), "static": z.get("static", []), "dynamic": z.get("dynamic", [])}
        for z in structured.get("zones", [])
    ]
    # 통일 체크리스트는 단일 원본(checklist.json)에서 파생. (레거시 .md는 더 이상 생성되지 않음)
    static_items = checklist_store.flatten_categories(structured.get("static", {}).get("categories", []))
    dynamic_items = checklist_store.flatten_categories(structured.get("dynamic", {}).get("categories", []))
    return {
        "static": checklist_store.format_numbered(static_items),
        "dynamic": checklist_store.format_numbered(dynamic_items),
        "zones": zones,
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
        raise HTTPException(status_code=403, detail="현장이 지정되지 않은 계정입니다.")
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
        static_categories = await normalize_categories(static_items, "static")
        dynamic_categories = await normalize_categories(dynamic_items, "dynamic")
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
        raise HTTPException(status_code=403, detail="현장이 지정되지 않은 계정입니다.")
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
        raise HTTPException(status_code=403, detail="현장이 지정되지 않은 계정입니다.")
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
    """확정된 체크리스트를 checklist.json(단일 원본) + 파생물로 저장."""
    sid = _effective_site_id(current_user, site_id)
    if sid is None:
        raise HTTPException(status_code=403, detail="현장이 지정되지 않은 계정입니다.")

    # 인라인 편집 결과(추가/수정/삭제)를 반영한 최종 항목 기준으로 카테고리 코드를 재산정.
    # → 확정 시점에 카테고리 코드가 항상 현재 항목과 일치(편집된 항목도 올바른 코드 부여).
    static_items = [i.strip() for i in body.static if i and i.strip()]
    dynamic_items = [i.strip() for i in body.dynamic if i and i.strip()]
    try:
        static_cats = await normalize_categories(static_items, "static")
        dynamic_cats = await normalize_categories(dynamic_items, "dynamic")
    except Exception as e:
        logger.warning("카테고리 재산정 실패, GENERAL fallback: %s", e)
        static_cats = [{"code": "GENERAL", "label": "일반", "items": static_items}] if static_items else []
        dynamic_cats = [{"code": "GENERAL", "label": "일반", "items": dynamic_items}] if dynamic_items else []

    data = {
        "static": {"categories": static_cats},
        "dynamic": {"categories": dynamic_cats},
        "zones": [
            {"zone": z.zone,
             "static": [i.strip() for i in z.static if i and i.strip()],
             "dynamic": [i.strip() for i in z.dynamic if i and i.strip()]}
            for z in body.zones
        ],
    }

    await checklist_store.persist(_site_dir(sid), _get_redis(), str(sid), data)

    logger.info("체크리스트 저장 완료: site=%s static=%d dynamic=%d zones=%d",
                sid, len(body.static), len(body.dynamic), len(body.zones))
    return {"status": "saved", "static_count": len(body.static), "dynamic_count": len(body.dynamic)}


@router.post("/analyze-diff")
async def analyze_diff(
    file: UploadFile = File(...),
    site_id: str | None = Query(None),
    current_user: User = Depends(require_admin),
) -> dict:
    """새 PDF를 분석해 기존 확정 체크리스트와 비교한 추가/삭제후보 반환."""
    sid = _effective_site_id(current_user, site_id)
    if sid is None:
        raise HTTPException(status_code=403, detail="현장이 지정되지 않은 계정입니다.")
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="PDF 파일만 분석 가능합니다.")

    content = await file.read()
    try:
        pdf_text = extract_text_from_pdf(content)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    try:
        result, _ = await analyze_pdf(pdf_text)
    except Exception as e:
        logger.error("증분 분석 실패: %s", e)
        raise HTTPException(status_code=500, detail="분석에 실패했습니다. 다시 시도해주세요.")

    def _flatten(section: list) -> list[str]:
        out: list[str] = []
        for entry in section:
            if isinstance(entry, dict):
                out.extend(entry.get("items", []))
            elif isinstance(entry, str):
                out.append(entry)
        return out

    new_static = _flatten(result.get("static", []))
    new_dynamic = _flatten(result.get("dynamic", []))

    existing = await checklist_store.load_structured(_site_dir(sid), _get_redis(), str(sid))
    old_static = checklist_store.flatten_categories(existing.get("static", {}).get("categories", []))
    old_dynamic = checklist_store.flatten_categories(existing.get("dynamic", {}).get("categories", []))

    return {
        "static": await diff_checklist(old_static, new_static),
        "dynamic": await diff_checklist(old_dynamic, new_dynamic),
    }


@router.post("/merge")
async def merge_checklist(
    body: MergeRequest,
    site_id: str | None = Query(None),
    current_user: User = Depends(require_admin),
) -> dict:
    """수락된 추가/삭제를 기존 체크리스트에 병합. 추가 항목은 구역 자동 배치."""
    sid = _effective_site_id(current_user, site_id)
    if sid is None:
        raise HTTPException(status_code=403, detail="현장이 지정되지 않은 계정입니다.")

    data = await checklist_store.load_structured(_site_dir(sid), _get_redis(), str(sid))
    checklist_store.apply_removes(data, body.static_remove, body.dynamic_remove)
    checklist_store.apply_adds(data, body.static_add, body.dynamic_add)

    # 새 항목만 구역 자동 배치 (구역이 등록돼 있고 추가가 있을 때만 LLM 호출)
    if data.get("zones") and (body.static_add or body.dynamic_add):
        mini = {
            "static": [{"items": body.static_add}],
            "dynamic": [{"items": body.dynamic_add}],
        }
        zone_meta = [{"zone": z["zone"], "description": ""} for z in data["zones"]]
        try:
            subsets = await subset_by_zones(mini, zone_meta)
            checklist_store.apply_zone_assignments(data, subsets)
        except Exception as e:
            logger.warning("구역 자동 배치 실패(공통만 병합): %s", e)

    await checklist_store.persist(_site_dir(sid), _get_redis(), str(sid), data)
    return {"status": "merged"}
