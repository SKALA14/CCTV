# Checklist Category 고도화 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 체크리스트 항목을 의미 기반으로 정규화해 동적 카테고리 코드를 생성하고, VLM이 그 코드를 `anomaly_type`으로 출력하도록 연결한다.

**Architecture:** `normalize_categories()` LLM 호출로 유사 항목을 묶어 카테고리 코드를 생성 → `confirm` 시 `.md` 파일에 `[CODE] 항목` 형식으로 저장 → VLM이 프롬프트에서 코드를 읽고 `anomaly_type`으로 출력. DB·프론트엔드·`vlm/client.py` 변경 없음.

**Tech Stack:** Python, FastAPI, OpenAI AsyncOpenAI, pytest, pytest-asyncio

---

## 파일 구조

| 파일 | 역할 | 작업 |
|------|------|------|
| `services/backend/app/api/agent/checklist_agent.py` | `normalize_categories()` 추가 | 수정 |
| `services/backend/app/api/manuals.py` | `CategoryItem` 스키마, `/analyze` 응답, `/confirm` 저장 로직 수정 | 수정 |
| `services/backend/tests/test_normalize_categories.py` | `normalize_categories()` 단위 테스트 | 신규 생성 |
| `services/backend/tests/test_format_checklist.py` | `_format_checklist()` 단위 테스트 | 신규 생성 |
| `services/inference/prompts/static_prompt.j2` | anomaly_type 안내 문구 수정 | 수정 |
| `services/inference/prompts/dynamic_prompt.j2` | anomaly_type 안내 문구 수정 | 수정 |

---

## Task 1: `normalize_categories()` 테스트 작성

**Files:**
- Create: `services/backend/tests/test_normalize_categories.py`

- [ ] **Step 1: 테스트 파일 생성**

```python
# services/backend/tests/test_normalize_categories.py
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _make_mock_response(categories: list) -> MagicMock:
    mock_resp = MagicMock()
    mock_resp.choices[0].message.content = json.dumps(
        {"categories": categories}, ensure_ascii=False
    )
    return mock_resp


@pytest.mark.asyncio
async def test_normalize_categories_groups_similar_items():
    """의미가 유사한 항목들이 같은 카테고리로 묶이는지 확인."""
    mock_resp = _make_mock_response([
        {"code": "PPE_MISSING", "label": "보호장비 미착용",
         "items": ["안전복장 미착용인가?", "구명복 미착용인가?"]},
        {"code": "ACCESS_VIOLATION", "label": "출입통제 위반",
         "items": ["크레인 작업반경 내 무단출입인가?"]},
    ])

    with patch("app.api.agent.checklist_agent._get_openai") as mock_get:
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_resp)
        mock_get.return_value = mock_client

        from app.api.agent.checklist_agent import normalize_categories
        result = await normalize_categories(
            ["안전복장 미착용인가?", "구명복 미착용인가?", "크레인 작업반경 내 무단출입인가?"]
        )

    assert len(result) == 2
    ppe = next(c for c in result if c["code"] == "PPE_MISSING")
    assert len(ppe["items"]) == 2
    assert "안전복장 미착용인가?" in ppe["items"]
    assert "구명복 미착용인가?" in ppe["items"]


@pytest.mark.asyncio
async def test_normalize_categories_empty_input():
    """빈 입력이면 LLM 호출 없이 빈 배열 반환."""
    from app.api.agent.checklist_agent import normalize_categories
    result = await normalize_categories([])
    assert result == []


@pytest.mark.asyncio
async def test_normalize_categories_fallback_on_empty_response():
    """LLM이 빈 응답 반환 시 GENERAL 카테고리 단일 반환."""
    mock_resp = MagicMock()
    mock_resp.choices[0].message.content = ""

    with patch("app.api.agent.checklist_agent._get_openai") as mock_get:
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_resp)
        mock_get.return_value = mock_client

        from app.api.agent.checklist_agent import normalize_categories
        items = ["항목1?", "항목2?"]
        result = await normalize_categories(items)

    assert len(result) == 1
    assert result[0]["code"] == "GENERAL"
    assert result[0]["items"] == items


@pytest.mark.asyncio
async def test_normalize_categories_missing_items_get_uncategorized():
    """LLM이 일부 항목 누락 시 UNCATEGORIZED로 자동 보완."""
    mock_resp = _make_mock_response([
        {"code": "PPE_MISSING", "label": "보호장비 미착용", "items": ["항목1?"]},
        # 항목2? 누락
    ])

    with patch("app.api.agent.checklist_agent._get_openai") as mock_get:
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_resp)
        mock_get.return_value = mock_client

        from app.api.agent.checklist_agent import normalize_categories
        result = await normalize_categories(["항목1?", "항목2?"])

    codes = [c["code"] for c in result]
    assert "UNCATEGORIZED" in codes
    uncategorized = next(c for c in result if c["code"] == "UNCATEGORIZED")
    assert "항목2?" in uncategorized["items"]


@pytest.mark.asyncio
async def test_normalize_categories_fallback_on_api_error():
    """API 오류 시 GENERAL 카테고리로 fallback, 예외 전파 없음."""
    with patch("app.api.agent.checklist_agent._get_openai") as mock_get:
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(side_effect=Exception("API 오류"))
        mock_get.return_value = mock_client

        from app.api.agent.checklist_agent import normalize_categories
        items = ["항목1?"]
        result = await normalize_categories(items)

    assert len(result) == 1
    assert result[0]["code"] == "GENERAL"
    assert result[0]["items"] == items
```

- [ ] **Step 2: 테스트 실행 — FAIL 확인**

```bash
cd services/backend
python -m pytest tests/test_normalize_categories.py -v
```

Expected: `ImportError: cannot import name 'normalize_categories'`

---

## Task 2: `normalize_categories()` 구현

**Files:**
- Modify: `services/backend/app/api/agent/checklist_agent.py`

- [ ] **Step 1: `_NORMALIZE_SYSTEM` 프롬프트 상수와 `normalize_categories()` 추가**

`checklist_agent.py` 파일 맨 끝에 아래 코드를 추가한다. (기존 코드 변경 없음)

```python
_NORMALIZE_SYSTEM = (
    "다음은 CCTV 안전 체크리스트 항목들이다.\n"
    "의미가 겹치거나 같은 위험 유형에 속하는 항목들을 묶어 카테고리를 만들어라.\n\n"
    "[규칙]\n"
    "- 카테고리 코드: 영문+언더스코어, 20자 이내, 명사형 (예: PPE_MISSING, ACCESS_VIOLATION)\n"
    "- 의미가 명확히 다른 항목은 별도 카테고리로 분리\n"
    "- 항목이 1개만 있어도 카테고리로 만들 것\n"
    "- 항목 원문은 절대 수정하지 말 것\n\n"
    '{"categories": [{"code": "...", "label": "...(한국어 명사형)", "items": ["원문 질문?"]}]}'
)


async def normalize_categories(items: list[str]) -> list[dict]:
    """항목 리스트를 의미 기반으로 카테고리 코드와 함께 묶어 반환.

    반환: [{"code": "PPE_MISSING", "label": "보호장비 미착용", "items": [...]}]
    빈 입력이면 [] 반환. API 오류·파싱 실패 시 GENERAL 단일 카테고리로 fallback.
    """
    if not items:
        return []

    messages = [
        {"role": "system", "content": _NORMALIZE_SYSTEM},
        {"role": "user", "content": json.dumps(items, ensure_ascii=False)},
    ]
    try:
        resp = await _get_openai().chat.completions.create(
            model=_MODEL,
            messages=messages,
            response_format={"type": "json_object"},
        )
        raw = resp.choices[0].message.content or ""
        if not raw:
            return [{"code": "GENERAL", "label": "일반", "items": items}]

        data = json.loads(raw)
        categories = data.get("categories", [])
        if not categories:
            return [{"code": "GENERAL", "label": "일반", "items": items}]

        # 누락 항목 보완
        categorized = {item for cat in categories for item in cat.get("items", [])}
        missing = [item for item in items if item not in categorized]
        if missing:
            categories.append({"code": "UNCATEGORIZED", "label": "미분류", "items": missing})

        return categories

    except Exception as e:
        logger.warning("카테고리 정규화 실패: %s", e)
        return [{"code": "GENERAL", "label": "일반", "items": items}]
```

- [ ] **Step 2: 테스트 실행 — PASS 확인**

```bash
cd services/backend
python -m pytest tests/test_normalize_categories.py -v
```

Expected:
```
PASSED tests/test_normalize_categories.py::test_normalize_categories_groups_similar_items
PASSED tests/test_normalize_categories.py::test_normalize_categories_empty_input
PASSED tests/test_normalize_categories.py::test_normalize_categories_fallback_on_empty_response
PASSED tests/test_normalize_categories.py::test_normalize_categories_missing_items_get_uncategorized
PASSED tests/test_normalize_categories.py::test_normalize_categories_fallback_on_api_error
```

- [ ] **Step 3: 커밋**

```bash
git add services/backend/app/api/agent/checklist_agent.py \
        services/backend/tests/test_normalize_categories.py
git commit -m "feat: normalize_categories() 추가 — 체크리스트 항목 의미 기반 카테고리 정규화"
```

---

## Task 3: `_format_checklist()` 헬퍼 테스트 작성

**Files:**
- Create: `services/backend/tests/test_format_checklist.py`

- [ ] **Step 1: 테스트 파일 생성**

```python
# services/backend/tests/test_format_checklist.py


def test_format_checklist_with_categories():
    """카테고리 있을 때 [CODE] 태그 형식으로 반환."""
    from app.api.manuals import _format_checklist

    items = ["안전복장 미착용인가?", "크레인 작업반경 내 무단출입인가?"]

    class _Cat:
        def __init__(self, code, label, its):
            self.code = code
            self.label = label
            self.items = its

    categories = [
        _Cat("PPE_MISSING", "보호장비 미착용", ["안전복장 미착용인가?"]),
        _Cat("ACCESS_VIOLATION", "출입통제 위반", ["크레인 작업반경 내 무단출입인가?"]),
    ]
    result = _format_checklist(items, categories)

    assert "[PPE_MISSING] 안전복장 미착용인가?" in result
    assert "[ACCESS_VIOLATION] 크레인 작업반경 내 무단출입인가?" in result
    assert result.count("\n") == 1  # 2개 항목, 줄바꿈 1개


def test_format_checklist_without_categories():
    """카테고리 없을 때 기존 '- 항목' 형식으로 반환."""
    from app.api.manuals import _format_checklist

    items = ["항목1?", "항목2?"]
    result = _format_checklist(items, [])

    assert "- 항목1?" in result
    assert "- 항목2?" in result
    assert "[" not in result  # 태그 없어야 함


def test_format_checklist_item_not_in_any_category_uses_dash():
    """categories에 매핑되지 않은 항목은 '- 항목' 형식으로 fallback."""
    from app.api.manuals import _format_checklist

    class _Cat:
        def __init__(self, code, label, its):
            self.code = code
            self.label = label
            self.items = its

    items = ["항목1?", "매핑없음?"]
    categories = [_Cat("CODE_A", "라벨A", ["항목1?"])]
    result = _format_checklist(items, categories)

    assert "[CODE_A] 항목1?" in result
    assert "- 매핑없음?" in result


def test_format_checklist_empty_items():
    """빈 items면 빈 문자열 반환."""
    from app.api.manuals import _format_checklist
    assert _format_checklist([], []) == ""
```

- [ ] **Step 2: 테스트 실행 — FAIL 확인**

```bash
cd services/backend
python -m pytest tests/test_format_checklist.py -v
```

Expected: `ImportError: cannot import name '_format_checklist'`

---

## Task 4: `manuals.py` 스키마 및 헬퍼 추가

**Files:**
- Modify: `services/backend/app/api/manuals.py`

- [ ] **Step 1: `CategoryItem` 모델과 `_format_checklist()` 추가**

`manuals.py` 상단의 import 바로 아래, 기존 `RefineRequest` 클래스 위에 아래를 추가한다.

```python
class CategoryItem(BaseModel):
    code: str
    label: str
    items: list[str]
```

그리고 기존 `ConfirmRequest` 클래스를 아래로 교체한다.

```python
class ConfirmRequest(BaseModel):
    session_id: str
    static: list[str]
    dynamic: list[str]
    static_categories: list[CategoryItem] = []   # 없으면 기존 형식 유지
    dynamic_categories: list[CategoryItem] = []  # 없으면 기존 형식 유지
    zones: list[ZoneChecklist] = []
```

그리고 `_parse_zones()` 함수 바로 위에 `_format_checklist()` 헬퍼를 추가한다.

```python
def _format_checklist(items: list[str], categories: list) -> str:
    """카테고리 코드 태그를 포함한 체크리스트 텍스트 생성.

    categories가 없으면 기존 '- 항목' 형식 반환.
    categories에 없는 항목은 '- 항목' 형식으로 fallback.
    """
    if not items:
        return ""
    if not categories:
        return "\n".join(f"- {item}" for item in items)

    item_to_code: dict[str, str] = {}
    for cat in categories:
        for item in cat.items:
            item_to_code[item] = cat.code

    lines = []
    for item in items:
        code = item_to_code.get(item)
        lines.append(f"[{code}] {item}" if code else f"- {item}")
    return "\n".join(lines)
```

- [ ] **Step 2: import에 `normalize_categories` 추가**

`manuals.py` 상단 import 줄을 아래로 교체한다.

```python
from app.api.agent.checklist_agent import analyze_pdf, refine_checklist, subset_by_zones, normalize_categories
```

- [ ] **Step 3: 테스트 실행 — PASS 확인**

```bash
cd services/backend
python -m pytest tests/test_format_checklist.py -v
```

Expected:
```
PASSED tests/test_format_checklist.py::test_format_checklist_with_categories
PASSED tests/test_format_checklist.py::test_format_checklist_without_categories
PASSED tests/test_format_checklist.py::test_format_checklist_item_not_in_any_category_uses_dash
PASSED tests/test_format_checklist.py::test_format_checklist_empty_items
```

- [ ] **Step 4: 커밋**

```bash
git add services/backend/app/api/manuals.py \
        services/backend/tests/test_format_checklist.py
git commit -m "feat: CategoryItem 스키마, _format_checklist() 헬퍼 추가"
```

---

## Task 5: `/manuals/analyze` 엔드포인트 — categories 반환

**Files:**
- Modify: `services/backend/app/api/manuals.py` — `analyze_manual()` 함수

- [ ] **Step 1: `analyze_manual()` 함수 수정**

기존 `analyze_manual()` 함수의 return 구문을 아래로 교체한다.

```python
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
        "static": static_items,
        "dynamic": dynamic_items,
        "static_categories": static_categories,
        "dynamic_categories": dynamic_categories,
        "zones": zone_results,
    }
```

- [ ] **Step 2: 기존 테스트 전체 통과 확인**

```bash
cd services/backend
python -m pytest tests/ -v
```

Expected: 모든 기존 테스트 PASSED (새 테스트 포함)

- [ ] **Step 3: 커밋**

```bash
git add services/backend/app/api/manuals.py
git commit -m "feat: /manuals/analyze 응답에 static_categories, dynamic_categories 추가"
```

---

## Task 6: `/manuals/confirm` 엔드포인트 — 코드 태그 포함 저장

**Files:**
- Modify: `services/backend/app/api/manuals.py` — `confirm_manual()` 함수

- [ ] **Step 1: `confirm_manual()` 함수 수정**

기존 `confirm_manual()` 함수 전체를 아래로 교체한다.

```python
@router.post("/confirm")
async def confirm_manual(body: ConfirmRequest) -> dict:
    """확정된 체크리스트를 backend/prompts/에 저장.

    - 글로벌: {static,dynamic}_checklist.md — categories 있으면 [CODE] 태그 포함
    - 구역별: zone_{safe_name}_{static,dynamic}.md
    inference의 _load_checklist()가 같은 파일을 매 VLM 호출 시 읽음 — 즉시 반영.
    """
    prompts_dir = Path(config.PROMPTS_DIR)
    prompts_dir.mkdir(parents=True, exist_ok=True)

    (prompts_dir / _STATIC_FILE).write_text(
        _format_checklist(body.static, body.static_categories), encoding="utf-8"
    )
    (prompts_dir / _DYNAMIC_FILE).write_text(
        _format_checklist(body.dynamic, body.dynamic_categories), encoding="utf-8"
    )

    for z in body.zones:
        safe = z.zone.replace(" ", "_")

        # 구역 항목에 해당하는 카테고리만 필터링
        static_cats = [
            c for c in body.static_categories
            if any(item in z.static for item in c.items)
        ]
        dynamic_cats = [
            c for c in body.dynamic_categories
            if any(item in z.dynamic for item in c.items)
        ]

        (prompts_dir / f"zone_{safe}_static.md").write_text(
            _format_checklist(z.static, static_cats), encoding="utf-8"
        )
        (prompts_dir / f"zone_{safe}_dynamic.md").write_text(
            _format_checklist(z.dynamic, dynamic_cats), encoding="utf-8"
        )

    logger.info("체크리스트 저장 완료: static=%d, dynamic=%d, zones=%d",
                len(body.static), len(body.dynamic), len(body.zones))
    return {"status": "saved", "static_count": len(body.static), "dynamic_count": len(body.dynamic)}
```

- [ ] **Step 2: 저장 결과 수동 검증**

```bash
# 테스트용 confirm 요청 (categories 포함)
curl -X POST http://localhost:8000/manuals/confirm \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "test",
    "static": ["안전복장 미착용인가?", "구명복 미착용인가?"],
    "dynamic": ["크레인 작업반경 내 무단출입인가?"],
    "static_categories": [
      {"code": "PPE_MISSING", "label": "보호장비 미착용",
       "items": ["안전복장 미착용인가?", "구명복 미착용인가?"]}
    ],
    "dynamic_categories": [
      {"code": "ACCESS_VIOLATION", "label": "출입통제 위반",
       "items": ["크레인 작업반경 내 무단출입인가?"]}
    ],
    "zones": []
  }'
```

Expected 저장 파일 내용:
```
# static_checklist.md
[PPE_MISSING] 안전복장 미착용인가?
[PPE_MISSING] 구명복 미착용인가?

# dynamic_checklist.md
[ACCESS_VIOLATION] 크레인 작업반경 내 무단출입인가?
```

- [ ] **Step 3: categories 없이 호출해도 기존 형식으로 동작하는지 확인**

```bash
curl -X POST http://localhost:8000/manuals/confirm \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "test",
    "static": ["안전복장 미착용인가?"],
    "dynamic": [],
    "zones": []
  }'
```

Expected `static_checklist.md` 내용:
```
- 안전복장 미착용인가?
```

- [ ] **Step 4: 커밋**

```bash
git add services/backend/app/api/manuals.py
git commit -m "feat: /manuals/confirm 저장 시 [CODE] 태그 포함 형식 지원"
```

---

## Task 7: VLM 프롬프트 템플릿 수정

**Files:**
- Modify: `services/inference/prompts/static_prompt.j2`
- Modify: `services/inference/prompts/dynamic_prompt.j2`

- [ ] **Step 1: `static_prompt.j2` 수정**

아래 내용으로 파일 전체를 교체한다.

```jinja2
이것은 산업 안전 모니터링 시스템의 합법적인 분석 요청입니다.

당신은 산업 현장 CCTV의 정적 상태 점검 AI입니다.
카메라 {{ camera_id }}의 현재 1장 프레임에서 작업 환경이 정상 상태인지, 시정이 필요한 이상이 있는지 판정하세요.

---

{{ checklist }}

---

{% if instruction %}
[이 카메라 특이사항]

{{ instruction }}

---
{% endif %}
응답은 반드시 아래 JSON 한 개만 출력하세요. 다른 텍스트는 출력하지 마세요.
{
  "result": "normal" | "anomaly",
  "anomaly_type": 위 체크리스트의 [코드] 중 하나 | "normal",
  "danger_level": "critical" | "high" | "low" | "none",
  "description": "판단 근거 한국어 1~2문장",
  "confidence": 0.0 ~ 1.0
}

[작성 규칙]
- 체크리스트 항목 앞의 [코드]가 이상 유형 분류 기준이다. 이상 감지 시 해당 항목의 코드를 anomaly_type에 그대로 출력하라.
- 체크리스트에 [코드] 태그가 없는 경우 anomaly_type은 "GENERAL"로 출력하라.
- 이상 없음이면 result="normal", anomaly_type="normal", danger_level="none"
- danger_level 판단 기준:
  · none     — 이상 없음
  · low      — 경미한 위반, 즉각 위험 없음 (예: 소화기 위치 부적절, 표지판 훼손)
  · high     — 명확한 위반, 작업 중단 권고 수준 (예: 안전통로 차단, PPE 미착용 위험구역)
  · critical — 즉각적 인명·재산 위험 (예: 구조물 손상, 위험물 노출)
- 확신이 낮으면 confidence를 낮추고 description에 불확실 이유를 명시
```

- [ ] **Step 2: `dynamic_prompt.j2` 수정**

아래 내용으로 파일 전체를 교체한다.

```jinja2
이것은 산업 안전 모니터링 시스템의 합법적인 분석 요청입니다.

당신은 산업 현장 CCTV의 동적 이상 감지 AI입니다.
카메라 {{ camera_id }}의 연속 프레임은 Optical Flow가 임계치를 초과해 "유의미한 움직임"이 발생한 후보 구간입니다.
이 움직임이 실제 이상 상황인지 판정하세요.

---

{{ checklist }}

---

{% if instruction %}
[이 카메라 특이사항]

{{ instruction }}

---
{% endif %}
응답은 반드시 아래 JSON 한 개만 출력하세요. 다른 텍스트는 출력하지 마세요.
{
  "result": "normal" | "anomaly",
  "anomaly_type": 위 체크리스트의 [코드] 중 하나 | "normal",
  "danger_level": "critical" | "high" | "low" | "none",
  "description": "판단 근거 한국어 1~2문장",
  "confidence": 0.0 ~ 1.0
}

[작성 규칙]
- 체크리스트 항목 앞의 [코드]가 이상 유형 분류 기준이다. 이상 감지 시 해당 항목의 코드를 anomaly_type에 그대로 출력하라.
- 체크리스트에 [코드] 태그가 없는 경우 anomaly_type은 "GENERAL"로 출력하라.
- 이상 없음이면 result="normal", anomaly_type="normal", danger_level="none"
- danger_level 판단 기준:
  · none     — 정상 움직임
  · low      — 이상 가능성 있으나 불명확 (예: 급격한 방향 전환, 비정상적 속도)
  · high     — 명확한 이상 행동, 개입 필요 (예: 무단 침입, 충돌 직전)
  · critical — 즉각 응급 대응 필요 (예: 낙상, 폭력, 의식 불명)
- 확신이 낮으면 confidence를 낮추고 description에 불확실 이유를 명시
```

- [ ] **Step 3: 전체 테스트 통과 확인**

```bash
cd services/backend
python -m pytest tests/ -v
```

Expected: 모든 테스트 PASSED

- [ ] **Step 4: 커밋**

```bash
git add services/inference/prompts/static_prompt.j2 \
        services/inference/prompts/dynamic_prompt.j2
git commit -m "feat: VLM 프롬프트 템플릿 — anomaly_type을 체크리스트 [코드] 기반으로 변경"
```

---

## Self-Review

**Spec coverage:**
- [x] `normalize_categories()` 추가 → Task 1, 2
- [x] `CategoryItem` 스키마, `ConfirmRequest` 확장 → Task 4
- [x] `_format_checklist()` 헬퍼 → Task 3, 4
- [x] `/analyze` 응답 categories 포함 → Task 5
- [x] `/confirm` 코드 태그 저장 → Task 6
- [x] 구역별 `.md` 파일도 코드 태그 포함 → Task 6
- [x] `.j2` 템플릿 anomaly_type 안내 변경 → Task 7
- [x] 하위 호환 (categories 없으면 기존 형식) → Task 4, 6

**Placeholder scan:** 없음

**Type consistency:**
- `normalize_categories()` → `list[dict]` 반환 (Task 2 구현, Task 5에서 호출 일치)
- `_format_checklist(items: list[str], categories: list)` → Task 3 테스트, Task 4 구현, Task 6 호출 일치
- `CategoryItem.items: list[str]` → Task 4 정의, Task 6 `c.items` 접근 일치
