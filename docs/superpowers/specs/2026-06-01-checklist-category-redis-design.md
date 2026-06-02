# 체크리스트 카테고리 Redis 분리 설계

**날짜**: 2026-06-01
**브랜치**: dev1-woos
**작성자**: brainstorming 세션

---

## 배경 및 문제 정의

### 현재 방식의 한계

이전 구현에서 카테고리 코드를 `.md` 파일에 태그로 포함시켰다.

```
[SAFETY_BARRIERS] 작업장 주변에 개구부 안전난간이 설치되어 있는가?
[SAFETY_SIGNS] 작업장에 안전표지가 부착되어 있는가?
```

VLM은 이미지 분석과 동시에 태그 코드까지 기억하고 출력해야 한다.  
체크리스트 항목이 늘어날수록 VLM의 attention이 분산되어 탐지 정확도가 저하될 수 있다.

### 해결 방향

- VLM에게는 **번호만 붙인 순수 체크리스트**만 전달
- VLM은 **위반 항목의 번호**(`violated_index`)만 출력
- 카테고리 코드 매핑은 **Redis에 별도 저장**, `_parse()` 단계에서 조회

---

## 설계 목표

1. VLM 프롬프트에서 코드 태그 제거 → 탐지 정확도 향상
2. 카테고리 코드는 Redis hash로 관리 → hot path 조회 최적화
3. 어떤 예외 상황에서도 탐지 파이프라인 중단 없음 (GENERAL fallback)
4. 하위 호환: categories 미전달 시 기존 번호 형식으로 동작

---

## 전체 데이터 흐름

```
[1] PDF 분석
    POST /manuals/analyze
         ├─ analyze_pdf()           # 기존 그대로
         └─ normalize_categories()  # 기존 그대로
              └─ 응답: static_categories, dynamic_categories

[2] 프론트 확정
    POST /manuals/confirm
         ├─ _format_checklist()     # 번호 형식으로 변경
         │   "1. 안전난간 설치되어 있는가?"
         │   "2. 안전표지 부착되어 있는가?"
         ├─ {track}_checklist.md 저장  (번호 형식)
         └─ HSET checklist:{track}:categories
               {"1": "SAFETY_BARRIERS", "2": "SAFETY_SIGNS"}

[3] VLM 탐지
    render_prompt()
         ├─ _load_checklist()       # 번호 형식 .md 읽기 (변경 없음)
         └─ hgetall checklist:{track}:categories → categories dict

[4] VLM 응답
    violated_index: "1"            # 번호만 출력 (anomaly_type 제거)

[5] _parse(raw_text, categories)
         └─ categories["1"] → anomaly_type = "SAFETY_BARRIERS"

[6] DB 저장 / Slack 알림
    event_logs.anomaly_type = "SAFETY_BARRIERS"  # 기존과 동일
```

---

## 컴포넌트별 설계

### 1. Redis 키 구조

```
# 글로벌
checklist:static:categories          hash  {"1": "SAFETY_BARRIERS", "2": "SAFETY_SIGNS"}
checklist:dynamic:categories         hash  {"1": "PPE_MISSING"}

# 구역별
checklist:zone_{safe_name}:static:categories   hash  {...}
checklist:zone_{safe_name}:dynamic:categories  hash  {...}
```

- `safe_name`: `zone.replace(" ", "_")`
- TTL 없음 — confirm 시 덮어씀
- `hgetall` 반환값: `{b"1": b"SAFETY_BARRIERS", ...}` → `str` decode 필요

---

### 2. `_format_checklist()` + `_build_categories_map()` (`manuals.py`)

**`_format_checklist()` 변경**

```python
def _format_checklist(items: list[str], categories: list) -> str:
    """번호 형식 체크리스트 텍스트 생성.
    categories 여부와 무관하게 항상 번호 형식 반환.
    """
    if not items:
        return ""
    return "\n".join(f"{i+1}. {item}" for i, item in enumerate(items))
```

**`_build_categories_map()` 신규 추가**

```python
def _build_categories_map(items: list[str], categories: list) -> dict[str, str]:
    """항목 인덱스(1-based) → 카테고리 코드 매핑 dict 생성.

    categories 없으면 빈 dict 반환.
    categories에 없는 항목은 "GENERAL"로 처리.
    """
    if not categories:
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

---

### 3. `confirm_manual()` 변경 (`manuals.py`)

```python
@router.post("/confirm")
async def confirm_manual(body: ConfirmRequest) -> dict:
    prompts_dir = Path(config.PROMPTS_DIR)
    prompts_dir.mkdir(parents=True, exist_ok=True)
    redis = get_async_redis()  # 기존 backend Redis 클라이언트

    # 글로벌 .md 저장 (번호 형식)
    (prompts_dir / _STATIC_FILE).write_text(
        _format_checklist(body.static, body.static_categories), encoding="utf-8"
    )
    (prompts_dir / _DYNAMIC_FILE).write_text(
        _format_checklist(body.dynamic, body.dynamic_categories), encoding="utf-8"
    )

    # 글로벌 categories → Redis
    static_map = _build_categories_map(body.static, body.static_categories)
    dynamic_map = _build_categories_map(body.dynamic, body.dynamic_categories)
    if static_map:
        await redis.delete("checklist:static:categories")
        await redis.hset("checklist:static:categories", mapping=static_map)
    if dynamic_map:
        await redis.delete("checklist:dynamic:categories")
        await redis.hset("checklist:dynamic:categories", mapping=dynamic_map)

    # 구역별 .md + Redis
    for z in body.zones:
        safe = z.zone.replace(" ", "_")
        static_cats = [c for c in body.static_categories if any(item in z.static for item in c.items)]
        dynamic_cats = [c for c in body.dynamic_categories if any(item in z.dynamic for item in c.items)]

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

    logger.info("체크리스트 저장 완료: static=%d dynamic=%d zones=%d",
                len(body.static), len(body.dynamic), len(body.zones))
    return {"status": "saved", "static_count": len(body.static), "dynamic_count": len(body.dynamic)}
```

---

### 4. `render_prompt()` + `_parse()` 변경 (`vlm/client.py`)

**`_parse()` — categories 파라미터 추가**

```python
def _parse(self, raw_text: str, categories: dict[str, str] | None = None) -> dict:
    normal = {
        "result": "normal", "anomaly_type": "normal",
        "danger_level": "none", "description": "", "confidence": 0.0,
    }
    # ... 기존 JSON 파싱 로직 유지 ...

    result = str(data.get("result", "normal"))
    if result == "normal":
        return {**normal, "description": str(data.get("description", ""))}

    # violated_index → anomaly_type 변환
    violated_index = str(data.get("violated_index", ""))
    if categories and violated_index:
        anomaly_type = categories.get(violated_index, "GENERAL")
    else:
        anomaly_type = str(data.get("anomaly_type", "GENERAL")) or "GENERAL"

    return {
        "result": "anomaly",
        "anomaly_type": anomaly_type,
        "danger_level": level if level in _VALID_LEVELS else "none",
        "description": str(data.get("description", "")),
        "confidence": float(max(0.0, min(1.0, data.get("confidence", 0.5)))),
    }
```

**`render_prompt()` — categories 조회 추가**

```python
def render_prompt(filename: str, camera_id: str) -> str:
    track = filename.split("_", 1)[0]
    instruction = get_client().get(f"camera_instruction:{camera_id}") or ""
    checklist = _load_checklist(track, camera_id)

    # categories Redis 조회
    categories_key = _get_categories_key(track, camera_id)
    try:
        raw_map = get_client().hgetall(categories_key)
        categories = {k.decode(): v.decode() for k, v in raw_map.items()} if raw_map else {}
    except Exception as e:
        logger.warning("categories 조회 실패: %s", e)
        categories = {}

    return _get_template(filename).render(
        camera_id=camera_id,
        instruction=instruction,
        checklist=checklist,
    ), categories  # tuple 반환


def _get_categories_key(track: str, camera_id: str) -> str:
    """카메라의 구역을 조회해 적절한 Redis 카테고리 키 반환."""
    zone = get_client().get(f"camera:{camera_id}:zone") or b""
    zone_str = zone.decode() if isinstance(zone, bytes) else zone
    if zone_str:
        safe = zone_str.replace(" ", "_")
        return f"checklist:zone_{safe}:{track}:categories"
    return f"checklist:{track}:categories"
```

**`analyze()` — categories 전달**

```python
def analyze(self, frame_paths: list[str], prompt: str, categories: dict | None = None) -> dict:
    if not frame_paths:
        return {"result": "normal", "anomaly_type": "normal",
                "danger_level": "none", "description": "", "confidence": 0.0}
    raw = self._predict(prompt, frame_paths)
    logger.debug("VLM raw: %s", raw[:200])
    return self._parse(raw, categories)
```

---

### 5. VLM 프롬프트 템플릿 변경

**`static_prompt.j2` / `dynamic_prompt.j2` 공통 변경**

```jinja2
응답은 반드시 아래 JSON 한 개만 출력하세요. 다른 텍스트는 출력하지 마세요.
{
  "result": "normal" | "anomaly",
  "violated_index": 위반 항목 번호(문자열) | null,
  "danger_level": "critical" | "high" | "low" | "none",
  "description": "판단 근거 한국어 1~2문장",
  "confidence": 0.0 ~ 1.0
}

[작성 규칙]
- 이상 감지 시 위반된 체크리스트 항목의 번호를 violated_index에 문자열로 출력 (예: "1", "3")
- 이상 없으면 result="normal", violated_index=null, danger_level="none"
- 항목 번호 하나만 출력 (복수 위반 시 가장 심각한 항목 하나 선택)
```

---

### 6. 예외 처리

| 상황 | 처리 |
|------|------|
| Redis 키 없음 (confirm 전) | `categories = {}` → `anomaly_type = "GENERAL"` |
| violated_index = null | `result = "normal"` 처리 |
| Redis 연결 실패 | `logger.warning` + `categories = {}` → fallback |
| VLM이 범위 밖 인덱스 출력 | `categories.get(idx, "GENERAL")` → `"GENERAL"` |
| categories 빈 dict | `anomaly_type = data.get("anomaly_type", "GENERAL")` 로 구버전 호환 |

---

## 변경 파일 목록

| 파일 | 변경 내용 | 규모 |
|------|-----------|------|
| `services/backend/app/api/manuals.py` | `_format_checklist()` 번호 형식 변경, `_build_categories_map()` 추가, `confirm_manual()` Redis HSET 추가 | 중 |
| `services/inference/vlm/client.py` | `_parse()` categories 파라미터, `render_prompt()` tuple 반환, `_get_categories_key()` 추가, `analyze()` categories 전달 | 중 |
| `services/inference/static/vlm_worker.py` | `render_prompt()` tuple unpacking → `vlm.analyze(frames, prompt, categories)` 호출 | 소 |
| `services/inference/dynamic/vlm_worker.py` | 동일 | 소 |
| `services/inference/prompts/static_prompt.j2` | `anomaly_type` → `violated_index` 출력으로 변경 | 소 |
| `services/inference/prompts/dynamic_prompt.j2` | 동일 | 소 |

**변경 없는 파일**: `checklist_agent.py`, `worker.py`, DB 모델, 프론트엔드, `slack.py`

---

## 하위 호환

- `categories` 빈 dict 시 → `data.get("anomaly_type")` 로 fallback (기존 [CODE] 태그 방식 호환)
- `violated_index` 없는 구버전 VLM 응답 → `anomaly_type` 필드 직접 사용
- confirm 전 Redis 키 없음 → `"GENERAL"` fallback, 서비스 중단 없음
