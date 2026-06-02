# Checklist Category Redis 분리 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 체크리스트 카테고리 코드를 `.md` 파일에서 분리해 Redis hash로 저장하고, VLM은 번호(violated_index)만 출력한 뒤 `_parse()`에서 Redis 조회로 anomaly_type을 결정한다.

**Architecture:** `confirm_manual()` 시 `.md`에 번호 형식(`1. 항목`) 저장 + Redis에 `checklist:{track}:categories` hash 저장 → `render_prompt()`가 (prompt, categories) 튜플 반환 → `_parse()`가 `violated_index`를 categories dict로 조회해 anomaly_type 결정.

**Tech Stack:** Python, FastAPI, redis-py (sync, decode_responses=True), redis.asyncio, pytest, pytest-asyncio

---

## 파일 구조

| 파일 | 역할 | 작업 |
|------|------|------|
| `services/backend/tests/test_format_checklist.py` | `_format_checklist()` 번호 형식 테스트 | 수정 |
| `services/backend/tests/test_build_categories_map.py` | `_build_categories_map()` 단위 테스트 | 신규 |
| `services/backend/app/api/manuals.py` | `_format_checklist()` + `_build_categories_map()` + `confirm_manual()` | 수정 |
| `services/inference/tests/test_vlm_parse.py` | `_parse()` 단위 테스트 | 신규 |
| `services/inference/vlm/client.py` | `_get_categories_key()` + `render_prompt()` tuple + `_parse()` + `analyze()` | 수정 |
| `services/inference/static/vlm_worker.py` | render_prompt 튜플 언패킹 + categories 전달 | 수정 |
| `services/inference/dynamic/vlm_worker.py` | 동일 | 수정 |
| `services/inference/prompts/static_prompt.j2` | violated_index 출력으로 변경 | 수정 |
| `services/inference/prompts/dynamic_prompt.j2` | 동일 | 수정 |

---

## Task 1: `_format_checklist()` 번호 형식으로 변경

**Files:**
- Modify: `services/backend/tests/test_format_checklist.py`
- Modify: `services/backend/app/api/manuals.py:60-80`

- [ ] **Step 1: `test_format_checklist.py` 전체를 새 내용으로 교체**

```python
# services/backend/tests/test_format_checklist.py


def test_format_checklist_with_categories_returns_numbered():
    """categories 여부와 무관하게 항상 번호 형식으로 반환."""
    from app.api.manuals import _format_checklist

    class _Cat:
        def __init__(self, code, label, its):
            self.code = code
            self.label = label
            self.items = its

    items = ["안전복장 미착용인가?", "크레인 작업반경 내 무단출입인가?"]
    categories = [
        _Cat("PPE_MISSING", "보호장비 미착용", ["안전복장 미착용인가?"]),
        _Cat("ACCESS_VIOLATION", "출입통제 위반", ["크레인 작업반경 내 무단출입인가?"]),
    ]
    result = _format_checklist(items, categories)

    assert "1. 안전복장 미착용인가?" in result
    assert "2. 크레인 작업반경 내 무단출입인가?" in result
    assert "[" not in result   # 코드 태그 없어야 함
    assert result.count("\n") == 1


def test_format_checklist_without_categories_returns_numbered():
    """categories 없어도 번호 형식으로 반환."""
    from app.api.manuals import _format_checklist

    items = ["항목1?", "항목2?"]
    result = _format_checklist(items, [])

    assert "1. 항목1?" in result
    assert "2. 항목2?" in result
    assert "[" not in result


def test_format_checklist_single_item():
    """항목 1개도 정상 처리."""
    from app.api.manuals import _format_checklist
    result = _format_checklist(["항목1?"], [])
    assert result == "1. 항목1?"


def test_format_checklist_empty_items():
    """빈 items면 빈 문자열 반환."""
    from app.api.manuals import _format_checklist
    assert _format_checklist([], []) == ""
```

- [ ] **Step 2: 테스트 실행 — FAIL 확인**

```bash
cd /Users/skala/workspace/CCTV/services/backend
python -m pytest tests/test_format_checklist.py -v
```

Expected: 기존 `[CODE]` 형식 검사 테스트들이 FAIL

- [ ] **Step 3: `_format_checklist()` 구현 변경 (`manuals.py:60-80`)**

```python
def _format_checklist(items: list[str], categories: list) -> str:
    """번호 형식 체크리스트 텍스트 생성.

    categories 여부와 무관하게 항상 번호 형식 반환.
    코드 매핑은 _build_categories_map()이 별도 처리.
    """
    if not items:
        return ""
    return "\n".join(f"{i + 1}. {item}" for i, item in enumerate(items))
```

- [ ] **Step 4: 테스트 실행 — PASS 확인**

```bash
cd /Users/skala/workspace/CCTV/services/backend
python -m pytest tests/test_format_checklist.py -v
```

Expected: 4 passed

- [ ] **Step 5: 커밋**

```bash
cd /Users/skala/workspace/CCTV
git add services/backend/tests/test_format_checklist.py \
        services/backend/app/api/manuals.py
git commit -m "feat: _format_checklist() 번호 형식으로 변경 — 코드 태그 제거"
```

---

## Task 2: `_build_categories_map()` TDD 구현

**Files:**
- Create: `services/backend/tests/test_build_categories_map.py`
- Modify: `services/backend/app/api/manuals.py` (함수 추가)

- [ ] **Step 1: 테스트 파일 생성**

```python
# services/backend/tests/test_build_categories_map.py


def test_build_categories_map_basic():
    """항목 인덱스(1-based) → 카테고리 코드 매핑 생성."""
    from app.api.manuals import _build_categories_map

    class _Cat:
        def __init__(self, code, its):
            self.code = code
            self.items = its

    items = ["안전난간 설치됐는가?", "안전표지 부착됐는가?", "작업발판 설치됐는가?"]
    categories = [
        _Cat("SAFETY_BARRIERS", ["안전난간 설치됐는가?", "작업발판 설치됐는가?"]),
        _Cat("SAFETY_SIGNS", ["안전표지 부착됐는가?"]),
    ]
    result = _build_categories_map(items, categories)
    assert result == {"1": "SAFETY_BARRIERS", "2": "SAFETY_SIGNS", "3": "SAFETY_BARRIERS"}


def test_build_categories_map_without_categories_returns_empty():
    """categories 없으면 빈 dict 반환."""
    from app.api.manuals import _build_categories_map
    assert _build_categories_map(["항목1?"], []) == {}


def test_build_categories_map_unmapped_item_gets_general():
    """categories에 없는 항목은 'GENERAL' 코드 부여."""
    from app.api.manuals import _build_categories_map

    class _Cat:
        def __init__(self, code, its):
            self.code = code
            self.items = its

    items = ["항목1?", "매핑없음?"]
    categories = [_Cat("CODE_A", ["항목1?"])]
    result = _build_categories_map(items, categories)
    assert result == {"1": "CODE_A", "2": "GENERAL"}


def test_build_categories_map_empty_items():
    """빈 items면 빈 dict 반환."""
    from app.api.manuals import _build_categories_map
    assert _build_categories_map([], []) == {}


def test_build_categories_map_keys_are_strings():
    """인덱스 키가 문자열('1', '2', ...)이어야 함 — Redis HSET mapping 호환."""
    from app.api.manuals import _build_categories_map

    class _Cat:
        def __init__(self, code, its):
            self.code = code
            self.items = its

    result = _build_categories_map(["항목?"], [_Cat("CODE", ["항목?"])])
    assert all(isinstance(k, str) for k in result.keys())
```

- [ ] **Step 2: 테스트 실행 — FAIL 확인**

```bash
cd /Users/skala/workspace/CCTV/services/backend
python -m pytest tests/test_build_categories_map.py -v
```

Expected: `ImportError: cannot import name '_build_categories_map'`

- [ ] **Step 3: `_build_categories_map()` 구현 (`manuals.py`의 `_format_checklist()` 바로 아래에 추가)**

```python
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
```

- [ ] **Step 4: 테스트 실행 — PASS 확인**

```bash
cd /Users/skala/workspace/CCTV/services/backend
python -m pytest tests/test_build_categories_map.py -v
```

Expected: 5 passed

- [ ] **Step 5: 전체 백엔드 테스트 통과 확인**

```bash
cd /Users/skala/workspace/CCTV/services/backend
python -m pytest tests/ -v
```

Expected: 모든 테스트 PASS

- [ ] **Step 6: 커밋**

```bash
cd /Users/skala/workspace/CCTV
git add services/backend/app/api/manuals.py \
        services/backend/tests/test_build_categories_map.py
git commit -m "feat: _build_categories_map() 추가 — 항목 인덱스→코드 매핑 dict 생성"
```

---

## Task 3: `confirm_manual()` Redis HSET 추가

**Files:**
- Modify: `services/backend/app/api/manuals.py:286-325` (`confirm_manual()` 함수)

- [ ] **Step 1: `confirm_manual()` 전체를 아래로 교체**

`manuals.py`의 `confirm_manual()` 함수(현재 line 286~325)를 찾아 전체 교체.

```python
@router.post("/confirm")
async def confirm_manual(body: ConfirmRequest) -> dict:
    """확정된 체크리스트를 backend/prompts/에 저장.

    - 글로벌: {static,dynamic}_checklist.md — 번호 형식 저장
    - 글로벌: Redis checklist:{track}:categories hash — 인덱스→코드 매핑
    - 구역별: zone_{safe_name}_{static,dynamic}.md + Redis zone hash
    inference의 _load_checklist()와 render_prompt()가 매 VLM 호출 시 읽음 — 즉시 반영.
    """
    prompts_dir = Path(config.PROMPTS_DIR)
    prompts_dir.mkdir(parents=True, exist_ok=True)
    redis = _get_redis()

    # 글로벌 .md 저장 (번호 형식)
    (prompts_dir / _STATIC_FILE).write_text(
        _format_checklist(body.static, body.static_categories), encoding="utf-8"
    )
    (prompts_dir / _DYNAMIC_FILE).write_text(
        _format_checklist(body.dynamic, body.dynamic_categories), encoding="utf-8"
    )

    # 글로벌 categories → Redis hash
    static_map = _build_categories_map(body.static, body.static_categories)
    dynamic_map = _build_categories_map(body.dynamic, body.dynamic_categories)
    if static_map:
        await redis.delete("checklist:static:categories")
        await redis.hset("checklist:static:categories", mapping=static_map)
    if dynamic_map:
        await redis.delete("checklist:dynamic:categories")
        await redis.hset("checklist:dynamic:categories", mapping=dynamic_map)

    # 구역별 .md + Redis hash
    for z in body.zones:
        safe = z.zone.replace(" ", "_")
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

        zone_static_map  = _build_categories_map(z.static,  static_cats)
        zone_dynamic_map = _build_categories_map(z.dynamic, dynamic_cats)
        if zone_static_map:
            await redis.delete(f"checklist:zone_{safe}:static:categories")
            await redis.hset(f"checklist:zone_{safe}:static:categories", mapping=zone_static_map)
        if zone_dynamic_map:
            await redis.delete(f"checklist:zone_{safe}:dynamic:categories")
            await redis.hset(f"checklist:zone_{safe}:dynamic:categories", mapping=zone_dynamic_map)

    logger.info("체크리스트 저장 완료: static=%d, dynamic=%d, zones=%d",
                len(body.static), len(body.dynamic), len(body.zones))
    return {"status": "saved", "static_count": len(body.static), "dynamic_count": len(body.dynamic)}
```

- [ ] **Step 2: 전체 백엔드 테스트 통과 확인**

```bash
cd /Users/skala/workspace/CCTV/services/backend
python -m pytest tests/ -v
```

Expected: 모든 테스트 PASS

- [ ] **Step 3: Redis 저장 수동 검증 (서버 실행 중일 때)**

```bash
# confirm 요청
curl -X POST http://localhost:8000/manuals/confirm \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "test",
    "static": ["안전난간 설치됐는가?", "안전표지 부착됐는가?"],
    "dynamic": [],
    "static_categories": [
      {"code": "SAFETY_BARRIERS", "label": "안전장벽", "items": ["안전난간 설치됐는가?"]},
      {"code": "SAFETY_SIGNS", "label": "안전표지", "items": ["안전표지 부착됐는가?"]}
    ],
    "zones": []
  }'

# Redis 확인
docker exec infra-redis-1 redis-cli HGETALL checklist:static:categories
```

Expected Redis 응답:
```
1) "1"
2) "SAFETY_BARRIERS"
3) "2"
4) "SAFETY_SIGNS"
```

Expected .md 파일:
```bash
docker exec infra-backend-1 cat /service/prompts/static_checklist.md
# 출력:
# 1. 안전난간 설치됐는가?
# 2. 안전표지 부착됐는가?
```

- [ ] **Step 4: 커밋**

```bash
cd /Users/skala/workspace/CCTV
git add services/backend/app/api/manuals.py
git commit -m "feat: confirm_manual() — 번호 형식 .md + Redis categories hash 저장"
```

---

## Task 4: `render_prompt()` tuple 반환 + `_get_categories_key()` 추가

**Files:**
- Modify: `services/inference/vlm/client.py:155-164`

> 배경: inference `redis_client.py`의 `get_client()`는 `decode_responses=True`로 초기화됨 → `hgetall()` 반환값이 이미 `dict[str, str]`이므로 별도 decode 불필요.

- [ ] **Step 1: `vlm/client.py`에 `_get_categories_key()` 추가 및 `render_prompt()` 수정**

`render_prompt()` 함수(현재 line 155-164)를 찾아 아래로 교체. `_get_categories_key()`는 바로 위에 추가.

```python
def _get_categories_key(track: str, camera_id: str) -> str:
    """카메라의 구역을 조회해 적절한 Redis 카테고리 키 반환.

    구역 있으면: checklist:zone_{safe_name}:{track}:categories
    구역 없으면: checklist:{track}:categories
    """
    zone = get_client().get(f"camera:{camera_id}:zone") or ""
    if zone:
        safe = zone.replace(" ", "_")
        return f"checklist:zone_{safe}:{track}:categories"
    return f"checklist:{track}:categories"


def render_prompt(filename: str, camera_id: str) -> tuple[str, dict[str, str]]:
    """camera_id, Redis camera_instruction, 체크리스트를 주입해 프롬프트 렌더링.

    반환: (rendered_prompt, categories_dict)
    categories_dict: {"1": "SAFETY_BARRIERS", "2": "SAFETY_SIGNS", ...}
    Redis 조회 실패 시 categories_dict = {} (anomaly_type fallback 처리는 _parse()가 담당)
    """
    track = filename.split("_", 1)[0]  # "dynamic_prompt.j2" → "dynamic"
    instruction = get_client().get(f"camera_instruction:{camera_id}") or ""
    checklist = _load_checklist(track, camera_id)

    categories_key = _get_categories_key(track, camera_id)
    try:
        categories: dict[str, str] = get_client().hgetall(categories_key) or {}
    except Exception as e:
        logger.warning("categories 조회 실패 (camera=%s): %s", camera_id, e)
        categories = {}

    prompt = _get_template(filename).render(
        camera_id=camera_id,
        instruction=instruction,
        checklist=checklist,
    )
    return prompt, categories
```

- [ ] **Step 2: 커밋**

```bash
cd /Users/skala/workspace/CCTV
git add services/inference/vlm/client.py
git commit -m "feat: render_prompt() tuple 반환 + _get_categories_key() 추가"
```

---

## Task 5: `_parse()` + `analyze()` — violated_index → anomaly_type 변환

**Files:**
- Create: `services/inference/tests/test_vlm_parse.py`
- Modify: `services/inference/vlm/client.py:69-122`

- [ ] **Step 1: 테스트 디렉토리 생성 및 테스트 파일 작성**

```bash
mkdir -p /Users/skala/workspace/CCTV/services/inference/tests
touch /Users/skala/workspace/CCTV/services/inference/tests/__init__.py
```

```python
# services/inference/tests/test_vlm_parse.py
"""VLMClient._parse() 단위 테스트 — categories dict를 통한 violated_index 매핑."""
import sys
from pathlib import Path

# inference 서비스 루트를 경로에 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

from unittest.mock import MagicMock, patch


def _make_client():
    """Redis/OpenAI 없이 VLMClient 인스턴스 생성."""
    with patch("vlm.client.config") as mock_cfg:
        mock_cfg.OPENAI_API_KEY = "test-key"
        mock_cfg.OPENAI_MODEL = "gpt-4o"
        with patch("vlm.client.OpenAI"):
            from vlm.client import VLMClient
            return VLMClient()


def test_parse_violated_index_maps_to_code():
    """violated_index + categories → anomaly_type 코드 변환."""
    client = _make_client()
    raw = '{"result": "anomaly", "violated_index": "2", "danger_level": "high", "description": "위반 감지", "confidence": 0.9}'
    categories = {"1": "SAFETY_BARRIERS", "2": "SAFETY_SIGNS"}
    result = client._parse(raw, categories)
    assert result["anomaly_type"] == "SAFETY_SIGNS"
    assert result["result"] == "anomaly"


def test_parse_normal_result_returns_normal():
    """result=normal이면 violated_index 무관하게 anomaly_type=normal."""
    client = _make_client()
    raw = '{"result": "normal", "violated_index": null, "danger_level": "none", "description": "", "confidence": 0.1}'
    result = client._parse(raw, {"1": "SAFETY_BARRIERS"})
    assert result["result"] == "normal"
    assert result["anomaly_type"] == "normal"


def test_parse_out_of_range_index_returns_general():
    """categories에 없는 인덱스면 GENERAL fallback."""
    client = _make_client()
    raw = '{"result": "anomaly", "violated_index": "99", "danger_level": "low", "description": "알 수 없음", "confidence": 0.5}'
    categories = {"1": "SAFETY_BARRIERS"}
    result = client._parse(raw, categories)
    assert result["anomaly_type"] == "GENERAL"


def test_parse_empty_categories_uses_general():
    """categories 빈 dict면 anomaly_type=GENERAL."""
    client = _make_client()
    raw = '{"result": "anomaly", "violated_index": "1", "danger_level": "high", "description": "위반", "confidence": 0.8}'
    result = client._parse(raw, {})
    assert result["anomaly_type"] == "GENERAL"


def test_parse_no_categories_param_uses_general():
    """categories 파라미터 없으면 GENERAL fallback."""
    client = _make_client()
    raw = '{"result": "anomaly", "violated_index": "1", "danger_level": "high", "description": "위반", "confidence": 0.8}'
    result = client._parse(raw)
    assert result["anomaly_type"] == "GENERAL"


def test_parse_invalid_json_returns_normal():
    """JSON 파싱 실패 시 normal fallback."""
    client = _make_client()
    result = client._parse("not json at all", {"1": "CODE"})
    assert result["result"] == "normal"
    assert result["anomaly_type"] == "normal"
```

- [ ] **Step 2: 테스트 실행 — FAIL 확인**

```bash
cd /Users/skala/workspace/CCTV/services/inference
python -m pytest tests/test_vlm_parse.py -v
```

Expected: `_parse()` 시그니처 불일치로 FAIL 또는 categories 조회 로직 없어서 FAIL

- [ ] **Step 3: `_parse()` + `analyze()` 수정 (`vlm/client.py:69-122`)**

`_parse()` 메서드(line 69~108)와 `analyze()` 메서드(line 110~122)를 찾아 아래로 교체.

```python
    def _parse(self, raw_text: str, categories: dict[str, str] | None = None) -> dict:
        """VLM 응답을 표준 dict로 파싱. 실패 시 normal fallback.

        categories: {"1": "SAFETY_BARRIERS", ...} — violated_index 조회용.
        categories 없거나 비어있으면 anomaly_type = "GENERAL" fallback.
        """
        normal = {
            "result": "normal",
            "anomaly_type": "normal",
            "danger_level": "none",
            "description": "",
            "confidence": 0.0,
        }

        if raw_text.find("{") == -1:
            lower = raw_text.lower()
            if any(p in lower for p in _REFUSAL_PHRASES):
                logger.warning("VLM 콘텐츠 정책 거부: %.100s", raw_text)
            else:
                logger.warning("VLM 응답에 JSON 없음: %.200s", raw_text)
            return normal

        try:
            start = raw_text.find("{")
            end = raw_text.rfind("}") + 1
            data = json.loads(raw_text[start:end])
        except json.JSONDecodeError as e:
            logger.warning("VLM JSON 파싱 실패: %s | %.200s", e, raw_text)
            return normal

        try:
            result = str(data.get("result", "normal"))
            level = data.get("danger_level", "none")

            if result != "anomaly":
                return {
                    "result": "normal",
                    "anomaly_type": "normal",
                    "danger_level": "none",
                    "description": str(data.get("description", "")),
                    "confidence": float(max(0.0, min(1.0, data.get("confidence", 0.5)))),
                }

            # violated_index → anomaly_type 변환
            violated_index = str(data.get("violated_index") or "").strip()
            if categories and violated_index:
                anomaly_type = categories.get(violated_index, "GENERAL")
            else:
                anomaly_type = "GENERAL"

            return {
                "result": "anomaly",
                "anomaly_type": anomaly_type,
                "danger_level": level if level in _VALID_LEVELS else "none",
                "description": str(data.get("description", "")),
                "confidence": float(max(0.0, min(1.0, data.get("confidence", 0.5)))),
            }
        except (ValueError, TypeError) as e:
            logger.warning("VLM 값 변환 실패: %s | data: %s", e, data)
            return normal

    def analyze(self, frame_paths: list[str], prompt: str, categories: dict[str, str] | None = None) -> dict:
        """이미지 리스트와 prompt로 VLM 분석 수행. 결과 dict 반환."""
        if not frame_paths:
            return {
                "result": "normal",
                "anomaly_type": "normal",
                "danger_level": "none",
                "description": "",
                "confidence": 0.0,
            }
        raw = self._predict(prompt, frame_paths)
        logger.debug("VLM raw: %s", raw[:200])
        return self._parse(raw, categories)
```

- [ ] **Step 4: 테스트 실행 — PASS 확인**

```bash
cd /Users/skala/workspace/CCTV/services/inference
python -m pytest tests/test_vlm_parse.py -v
```

Expected: 6 passed

- [ ] **Step 5: 커밋**

```bash
cd /Users/skala/workspace/CCTV
git add services/inference/vlm/client.py \
        services/inference/tests/__init__.py \
        services/inference/tests/test_vlm_parse.py
git commit -m "feat: _parse() violated_index→anomaly_type 변환 + analyze() categories 파라미터 추가"
```

---

## Task 6: Static/Dynamic 워커 — render_prompt 튜플 언패킹

**Files:**
- Modify: `services/inference/static/vlm_worker.py:50-55`
- Modify: `services/inference/dynamic/vlm_worker.py:44-47`

- [ ] **Step 1: `static/vlm_worker.py` 수정**

`analyze_camera()` 함수 내 `render_prompt` 호출부(line 50~55)를 찾아 교체.

```python
async def analyze_camera(vlm: VLMClient, prompt_file: str, camera_id: str) -> None:
    """단일 카메라에 대한 static VLM 호출. 이상 응답이면 events 발행."""
    frame_path = latest_frame_path(camera_id)
    if frame_path is None:
        return

    prompt, categories = render_prompt(prompt_file, camera_id)
    logger.info("[static.vlm] → VLM 호출: camera=%s", camera_id)
    t0 = time.monotonic()
    loop = asyncio.get_running_loop()
    try:
        result = await loop.run_in_executor(
            None, vlm.analyze, [frame_path], prompt, categories
        )
    except Exception as e:
        logger.error("[static.vlm] camera=%s analyze error: %s", camera_id, e)
        return
    elapsed = time.monotonic() - t0

    if result.get("result") == "normal":
        logger.info("[static.vlm] ← normal (%.1fs): camera=%s", elapsed, camera_id)
        return

    xadd(config.EVENTS_STREAM, {
        "camera_id": camera_id,
        "track": "static",
        "anomaly_type": result.get("anomaly_type", "normal"),
        "danger_level": result.get("danger_level", "none"),
        "description": result.get("description", ""),
        "timestamp": str(time.time()),
        "frame_path": frame_path,
    }, maxlen=config.EVENTS_MAXLEN)
    logger.info("[static.vlm] ← anomaly (%.1fs): camera=%s type=%s",
                elapsed, camera_id, result.get("anomaly_type"))
```

- [ ] **Step 2: `dynamic/vlm_worker.py` 수정**

`run()` 함수 내 `render_prompt` + `vlm.analyze` 호출부(line 44~47)를 찾아 교체.

```python
            frame_paths = [fp for _, fp, _ in frames][:config.GENERAL_BUFFER_SIZE]
            timestamp = frames[0][2]
            prompt, categories = render_prompt(config.DYNAMIC_PROMPT_FILE, cam_id)
            logger.info("[dynamic.vlm] → VLM 호출: camera=%s frames=%d", cam_id, len(frame_paths))
            t0 = time.monotonic()
            result = vlm.analyze(frame_paths, prompt, categories)
            elapsed = time.monotonic() - t0
```

- [ ] **Step 3: 백엔드 테스트 전체 통과 확인 (inference 테스트 포함)**

```bash
cd /Users/skala/workspace/CCTV/services/backend
python -m pytest tests/ -v

cd /Users/skala/workspace/CCTV/services/inference
python -m pytest tests/ -v
```

Expected: 모든 테스트 PASS

- [ ] **Step 4: 커밋**

```bash
cd /Users/skala/workspace/CCTV
git add services/inference/static/vlm_worker.py \
        services/inference/dynamic/vlm_worker.py
git commit -m "feat: static/dynamic workers — render_prompt tuple 언패킹 + categories 전달"
```

---

## Task 7: VLM 프롬프트 템플릿 변경

**Files:**
- Modify: `services/inference/prompts/static_prompt.j2`
- Modify: `services/inference/prompts/dynamic_prompt.j2`

- [ ] **Step 1: `static_prompt.j2` 전체 교체**

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
  "violated_index": 위반 항목 번호(문자열) | null,
  "danger_level": "critical" | "high" | "low" | "none",
  "description": "판단 근거 한국어 1~2문장",
  "confidence": 0.0 ~ 1.0
}

[작성 규칙]
- 이상 감지 시 위반된 체크리스트 항목의 번호를 violated_index에 문자열로 출력하라 (예: "1", "3")
- 복수 위반 시 가장 심각한 항목 하나만 선택
- 이상 없으면 result="normal", violated_index=null, danger_level="none"
- danger_level 판단 기준:
  · none     — 이상 없음
  · low      — 경미한 위반, 즉각 위험 없음 (예: 소화기 위치 부적절, 표지판 훼손)
  · high     — 명확한 위반, 작업 중단 권고 수준 (예: 안전통로 차단, PPE 미착용 위험구역)
  · critical — 즉각적 인명·재산 위험 (예: 구조물 손상, 위험물 노출)
- 확신이 낮으면 confidence를 낮추고 description에 불확실 이유를 명시
```

- [ ] **Step 2: `dynamic_prompt.j2` 전체 교체**

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
  "violated_index": 위반 항목 번호(문자열) | null,
  "danger_level": "critical" | "high" | "low" | "none",
  "description": "판단 근거 한국어 1~2문장",
  "confidence": 0.0 ~ 1.0
}

[작성 규칙]
- 이상 감지 시 위반된 체크리스트 항목의 번호를 violated_index에 문자열로 출력하라 (예: "1", "3")
- 복수 위반 시 가장 심각한 항목 하나만 선택
- 이상 없으면 result="normal", violated_index=null, danger_level="none"
- danger_level 판단 기준:
  · none     — 정상 움직임
  · low      — 이상 가능성 있으나 불명확 (예: 급격한 방향 전환, 비정상적 속도)
  · high     — 명확한 이상 행동, 개입 필요 (예: 무단 침입, 충돌 직전)
  · critical — 즉각 응급 대응 필요 (예: 낙상, 폭력, 의식 불명)
- 확신이 낮으면 confidence를 낮추고 description에 불확실 이유를 명시
```

- [ ] **Step 3: 전체 테스트 통과 확인**

```bash
cd /Users/skala/workspace/CCTV/services/backend
python -m pytest tests/ -v

cd /Users/skala/workspace/CCTV/services/inference
python -m pytest tests/ -v
```

Expected: 모든 테스트 PASS

- [ ] **Step 4: 커밋**

```bash
cd /Users/skala/workspace/CCTV
git add services/inference/prompts/static_prompt.j2 \
        services/inference/prompts/dynamic_prompt.j2
git commit -m "feat: VLM 프롬프트 — anomaly_type 제거, violated_index 출력으로 변경"
```

---

## Self-Review

**Spec coverage:**
- [x] `.md` 번호 형식 저장 → Task 1
- [x] `_build_categories_map()` 인덱스→코드 매핑 → Task 2
- [x] `confirm_manual()` Redis HSET → Task 3
- [x] `render_prompt()` tuple 반환 + `_get_categories_key()` → Task 4
- [x] `_parse()` violated_index 조회 + fallback → Task 5
- [x] workers tuple 언패킹 + categories 전달 → Task 6
- [x] 프롬프트 템플릿 violated_index → Task 7
- [x] 구역별 Redis hash → Task 3 (zone 루프)
- [x] Redis 연결 실패 fallback → Task 4 (try/except), Task 5 (categories=None)
- [x] 범위 밖 인덱스 fallback GENERAL → Task 5 (categories.get fallback)

**Placeholder scan:** 없음

**Type consistency:**
- `_build_categories_map()` → `dict[str, str]` → Task 3 `hset(mapping=...)` 호환 ✅
- `render_prompt()` → `tuple[str, dict[str, str]]` → Task 6 workers `prompt, categories = ...` ✅
- `analyze(frame_paths, prompt, categories=None)` → Task 6 `vlm.analyze([frame_path], prompt, categories)` ✅
- `run_in_executor(None, vlm.analyze, [frame_path], prompt, categories)` → positional args로 전달 ✅
