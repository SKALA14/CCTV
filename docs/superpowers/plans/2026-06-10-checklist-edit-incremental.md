# 체크리스트 직접 편집 + 메뉴얼 증분 업데이트 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 확정 체크리스트를 구조화 JSON 단일 원본으로 만들어 (1) 사람이 직접 편집하고 (2) 새 메뉴얼과 diff해 추가/삭제만 증분 병합할 수 있게 한다.

**Architecture:** 현장별 `checklist.json`을 단일 원본으로 두고, 인퍼런스가 읽는 `.md` 파일 + Redis 카테고리 맵은 저장 시 항상 파생 생성한다. 순수 로직(`checklist_store.py`)과 에이전트 diff(`checklist_agent.py`)를 분리해 OpenAI/Redis를 주입·모킹 가능하게 만들고, FastAPI 엔드포인트는 얇은 글루로 둔다.

**Tech Stack:** FastAPI, Redis(asyncio), OpenAI(AsyncOpenAI), pytest+AsyncMock, Vue3/Pinia(프론트, 테스트 하니스 없음 → 수동 검증)

**Branch:** `dev2` (이미 생성됨, dev1 `a423337`에서 분기)

---

## 파일 구조

| 파일 | 책임 |
|---|---|
| `services/backend/app/api/checklist_store.py` (신규) | 구조화 JSON ↔ 파생물(.md/Redis) 변환·저장·로드·증분 병합의 **순수/주입 가능 로직** |
| `services/backend/app/api/agent/checklist_agent.py` (수정) | `diff_checklist()` 추가 (의미 기반 list-vs-list diff) |
| `services/backend/app/api/manuals.py` (수정) | confirm 리팩터(store 사용) + F1 `GET/PUT checklist/full` + F2 `analyze-diff`/`merge` 엔드포인트 |
| `services/backend/tests/test_checklist_store.py` (신규) | store 순수 로직 단위테스트 |
| `services/backend/tests/test_diff_checklist.py` (신규) | diff 에이전트 단위테스트 |
| `services/frontend/src/api/manuals.js` (수정) | 4개 API 함수 추가 |
| `services/frontend/src/views/ManualView.vue` (수정) | F1 인라인 편집 UI + F2 모드선택/diff 리뷰 UI |
| `services/frontend/src/components/manual/ChecklistEditor.vue` (신규) | 편집 가능한 체크리스트 리스트(공통+구역) |
| `services/frontend/src/components/manual/DiffReview.vue` (신규) | 추가/삭제후보 체크박스 리뷰 |

### 구조화 JSON 형태 (단일 원본 `{PROMPTS_DIR}/{site}/checklist.json`)

```jsonc
{
  "static":  { "categories": [ { "code": "FIRE", "label": "소방", "items": ["...?"] } ] },
  "dynamic": { "categories": [ { "code": "FALL", "label": "낙상", "items": ["...?"] } ] },
  "zones":   [ { "zone": "정문", "static": ["...?"], "dynamic": ["...?"] } ]
}
```

평탄화 항목 리스트 = categories의 items를 순서대로 이은 것(별도 저장 안 함). 파생물(`.md`/Redis)은 현재 `confirm_manual`이 만드는 것과 **바이트 동일**해야 한다(인퍼런스 회귀 금지).

---

## Task 1: checklist_store 순수 변환 헬퍼

**Files:**
- Create: `services/backend/app/api/checklist_store.py`
- Test: `services/backend/tests/test_checklist_store.py`

- [ ] **Step 1: 실패하는 테스트 작성**

`services/backend/tests/test_checklist_store.py`:
```python
from app.api.checklist_store import (
    flatten_categories, format_numbered, item_to_code, categories_map, items_map,
)


def test_flatten_categories_preserves_order():
    cats = [
        {"code": "A", "label": "에이", "items": ["q1?", "q2?"]},
        {"code": "B", "label": "비", "items": ["q3?"]},
    ]
    assert flatten_categories(cats) == ["q1?", "q2?", "q3?"]


def test_format_numbered_matches_legacy_format():
    assert format_numbered(["q1?", "q2?"]) == "1. q1?\n2. q2?"
    assert format_numbered([]) == ""
    assert "[" not in format_numbered(["q1?"])  # 코드 태그 없음


def test_item_to_code_maps_each_item():
    cats = [{"code": "A", "label": "에이", "items": ["q1?", "q2?"]}]
    assert item_to_code(cats) == {"q1?": "A", "q2?": "A"}


def test_categories_map_is_1based_index_to_code():
    cats = [
        {"code": "A", "label": "에이", "items": ["q1?"]},
        {"code": "B", "label": "비", "items": ["q2?"]},
    ]
    assert categories_map(cats) == {"1": "A", "2": "B"}
    assert categories_map([]) == {}


def test_items_map_uses_lookup_default_general():
    lookup = {"q1?": "A"}
    assert items_map(["q1?", "q99?"], lookup) == {"1": "A", "2": "GENERAL"}
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd services/backend && python -m pytest tests/test_checklist_store.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.api.checklist_store'`

- [ ] **Step 3: 최소 구현**

`services/backend/app/api/checklist_store.py`:
```python
"""체크리스트 구조화 JSON ↔ 파생물(.md/Redis) 변환·저장·로드·병합.

순수 함수 + Redis를 인자로 주입받는 async 함수로 구성해 단위테스트가 쉽다.
구조화 JSON 형태:
  {"static": {"categories": [{"code","label","items":[...]}]},
   "dynamic": {"categories": [...]},
   "zones": [{"zone","static":[...],"dynamic":[...]}]}
"""

from __future__ import annotations


def flatten_categories(categories: list[dict]) -> list[str]:
    """카테고리 리스트에서 항목 문자열을 순서대로 평탄화."""
    out: list[str] = []
    for cat in categories:
        out.extend(cat.get("items", []))
    return out


def format_numbered(items: list[str]) -> str:
    """번호 형식 텍스트. 인퍼런스가 읽는 .md 포맷과 동일."""
    if not items:
        return ""
    return "\n".join(f"{i + 1}. {item}" for i, item in enumerate(items))


def item_to_code(categories: list[dict]) -> dict[str, str]:
    """항목 문자열 → 카테고리 코드 lookup."""
    lookup: dict[str, str] = {}
    for cat in categories:
        code = cat.get("code", "GENERAL")
        for item in cat.get("items", []):
            lookup[item] = code
    return lookup


def categories_map(categories: list[dict]) -> dict[str, str]:
    """1-based 인덱스(str) → 코드. Redis HSET용. 빈 입력이면 {}."""
    items = flatten_categories(categories)
    if not items:
        return {}
    lookup = item_to_code(categories)
    return {str(i + 1): lookup.get(item, "GENERAL") for i, item in enumerate(items)}


def items_map(items: list[str], lookup: dict[str, str]) -> dict[str, str]:
    """구역 항목 리스트 → 1-based 인덱스(str)→코드. lookup에 없으면 GENERAL."""
    if not items:
        return {}
    return {str(i + 1): lookup.get(item, "GENERAL") for i, item in enumerate(items)}
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd services/backend && python -m pytest tests/test_checklist_store.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: 커밋**

```bash
git add services/backend/app/api/checklist_store.py services/backend/tests/test_checklist_store.py
git commit -m "feat(checklist): 구조화 변환 순수 헬퍼 + 테스트"
```

---

## Task 2: persist() — JSON 저장 + .md/Redis 파생 생성

**Files:**
- Modify: `services/backend/app/api/checklist_store.py`
- Test: `services/backend/tests/test_checklist_store.py`

- [ ] **Step 1: 실패하는 테스트 작성** (test 파일 끝에 추가)

```python
import json
import pytest
from app.api.checklist_store import persist


class _FakeRedis:
    """hset/delete만 기록하는 인메모리 스텁."""
    def __init__(self):
        self.store: dict[str, dict] = {}

    async def delete(self, key):
        self.store.pop(key, None)

    async def hset(self, key, mapping=None):
        self.store.setdefault(key, {}).update(mapping or {})

    async def hgetall(self, key):
        return dict(self.store.get(key, {}))


def _sample_data():
    return {
        "static": {"categories": [{"code": "FIRE", "label": "소방", "items": ["소화기 가렸나?"]}]},
        "dynamic": {"categories": [{"code": "FALL", "label": "낙상", "items": ["쓰러졌나?"]}]},
        "zones": [{"zone": "정문 A", "static": ["소화기 가렸나?"], "dynamic": []}],
    }


@pytest.mark.asyncio
async def test_persist_writes_json_and_derived_md(tmp_path):
    redis = _FakeRedis()
    await persist(tmp_path, redis, "site1", _sample_data())

    # checklist.json 저장
    saved = json.loads((tmp_path / "checklist.json").read_text(encoding="utf-8"))
    assert saved["static"]["categories"][0]["code"] == "FIRE"

    # 파생 .md — 번호 형식, 코드 태그 없음
    assert (tmp_path / "static_checklist.md").read_text(encoding="utf-8") == "1. 소화기 가렸나?"
    assert (tmp_path / "dynamic_checklist.md").read_text(encoding="utf-8") == "1. 쓰러졌나?"

    # 파생 Redis 맵 (index→code)
    assert redis.store["checklist:site1:static:categories"] == {"1": "FIRE"}
    assert redis.store["checklist:site1:dynamic:categories"] == {"1": "FALL"}

    # 구역 파생 (공백 → _)
    assert (tmp_path / "zone_정문_A_static.md").read_text(encoding="utf-8") == "1. 소화기 가렸나?"
    assert redis.store["checklist:site1:zone_정문_A:static:categories"] == {"1": "FIRE"}


@pytest.mark.asyncio
async def test_persist_empty_section_clears_redis(tmp_path):
    redis = _FakeRedis()
    redis.store["checklist:site1:static:categories"] = {"1": "OLD"}
    data = {"static": {"categories": []}, "dynamic": {"categories": []}, "zones": []}
    await persist(tmp_path, redis, "site1", data)
    # 빈 섹션이면 키 제거(빈 맵 hset 안 함)
    assert "checklist:site1:static:categories" not in redis.store
    assert (tmp_path / "static_checklist.md").read_text(encoding="utf-8") == ""
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd services/backend && python -m pytest tests/test_checklist_store.py -k persist -v`
Expected: FAIL — `ImportError: cannot import name 'persist'`

- [ ] **Step 3: 구현** (checklist_store.py 끝에 추가)

```python
import json
from pathlib import Path


async def _write_map(redis, key: str, mapping: dict[str, str]) -> None:
    await redis.delete(key)
    if mapping:
        await redis.hset(key, mapping=mapping)


async def persist(site_dir: Path, redis, sid: str, data: dict) -> None:
    """구조화 JSON을 단일 원본으로 저장하고 .md/Redis 파생물을 재생성.

    site_dir: 현장 디렉토리(Path). redis: aioredis 호환(주입). sid: 현장 id 문자열.
    """
    site_dir = Path(site_dir)
    site_dir.mkdir(parents=True, exist_ok=True)

    (site_dir / "checklist.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    s_cats = data.get("static", {}).get("categories", [])
    d_cats = data.get("dynamic", {}).get("categories", [])
    s_items = flatten_categories(s_cats)
    d_items = flatten_categories(d_cats)

    (site_dir / "static_checklist.md").write_text(format_numbered(s_items), encoding="utf-8")
    (site_dir / "dynamic_checklist.md").write_text(format_numbered(d_items), encoding="utf-8")
    await _write_map(redis, f"checklist:{sid}:static:categories", categories_map(s_cats))
    await _write_map(redis, f"checklist:{sid}:dynamic:categories", categories_map(d_cats))

    s_lookup = item_to_code(s_cats)
    d_lookup = item_to_code(d_cats)
    for zone in data.get("zones", []):
        safe = zone["zone"].replace(" ", "_")
        zs = zone.get("static", [])
        zd = zone.get("dynamic", [])
        (site_dir / f"zone_{safe}_static.md").write_text(format_numbered(zs), encoding="utf-8")
        (site_dir / f"zone_{safe}_dynamic.md").write_text(format_numbered(zd), encoding="utf-8")
        await _write_map(redis, f"checklist:{sid}:zone_{safe}:static:categories", items_map(zs, s_lookup))
        await _write_map(redis, f"checklist:{sid}:zone_{safe}:dynamic:categories", items_map(zd, d_lookup))
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd services/backend && python -m pytest tests/test_checklist_store.py -v`
Expected: PASS (7 passed)

- [ ] **Step 5: 커밋**

```bash
git add services/backend/app/api/checklist_store.py services/backend/tests/test_checklist_store.py
git commit -m "feat(checklist): persist() — JSON 저장 + .md/Redis 파생 생성"
```

---

## Task 3: load_structured() — JSON 로드 + 레거시 역구성

**Files:**
- Modify: `services/backend/app/api/checklist_store.py`
- Test: `services/backend/tests/test_checklist_store.py`

기존 현장은 `checklist.json`이 없으므로, 있으면 그대로 읽고 없으면 `.md`+Redis+`zones.json`에서 1회 역구성한다(label은 code로 fallback).

- [ ] **Step 1: 실패하는 테스트 작성** (test 파일 끝에 추가)

```python
from app.api.checklist_store import load_structured, parse_numbered


def test_parse_numbered_extracts_items():
    assert parse_numbered("1. q1?\n2. q2?") == ["q1?", "q2?"]
    assert parse_numbered("") == []
    # 항목에 '. '가 포함돼도 첫 번호만 제거
    assert parse_numbered("1. a. b?") == ["a. b?"]


@pytest.mark.asyncio
async def test_load_structured_reads_existing_json(tmp_path):
    redis = _FakeRedis()
    await persist(tmp_path, redis, "s1", _sample_data())
    loaded = await load_structured(tmp_path, redis, "s1")
    assert loaded["static"]["categories"][0]["items"] == ["소화기 가렸나?"]


@pytest.mark.asyncio
async def test_load_structured_reconstructs_from_legacy(tmp_path):
    # checklist.json 없이 레거시 .md + redis 맵 + zones.json만 존재
    redis = _FakeRedis()
    (tmp_path / "static_checklist.md").write_text("1. 소화기 가렸나?\n2. 통로 막혔나?", encoding="utf-8")
    (tmp_path / "dynamic_checklist.md").write_text("1. 쓰러졌나?", encoding="utf-8")
    redis.store["checklist:s1:static:categories"] = {"1": "FIRE", "2": "FIRE"}
    redis.store["checklist:s1:dynamic:categories"] = {"1": "FALL"}
    (tmp_path / "zones.json").write_text(
        json.dumps([{"zone": "정문 A", "description": ""}], ensure_ascii=False), encoding="utf-8"
    )
    (tmp_path / "zone_정문_A_static.md").write_text("1. 소화기 가렸나?", encoding="utf-8")

    data = await load_structured(tmp_path, redis, "s1")

    # static: 같은 코드 FIRE로 묶임, label은 code fallback
    fire = data["static"]["categories"][0]
    assert fire["code"] == "FIRE"
    assert fire["label"] == "FIRE"
    assert fire["items"] == ["소화기 가렸나?", "통로 막혔나?"]
    assert data["dynamic"]["categories"][0]["items"] == ["쓰러졌나?"]
    # zone 복원
    assert data["zones"][0]["zone"] == "정문 A"
    assert data["zones"][0]["static"] == ["소화기 가렸나?"]
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd services/backend && python -m pytest tests/test_checklist_store.py -k "load_structured or parse_numbered" -v`
Expected: FAIL — `ImportError: cannot import name 'load_structured'`

- [ ] **Step 3: 구현** (checklist_store.py 끝에 추가)

```python
import re

_NUM_PREFIX = re.compile(r"^\s*\d+\.\s+")


def parse_numbered(text: str) -> list[str]:
    """번호 형식 .md 텍스트에서 항목 문자열 추출."""
    items: list[str] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        items.append(_NUM_PREFIX.sub("", line, count=1))
    return items


def _group_by_code(items: list[str], idx_to_code: dict[str, str]) -> list[dict]:
    """항목+(index→code) 맵으로 카테고리 리스트 재구성. 등장 순서 유지, label=code."""
    if not items:
        return []
    grouped: dict[str, dict] = {}
    order: list[str] = []
    for i, item in enumerate(items):
        code = idx_to_code.get(str(i + 1), "GENERAL")
        if code not in grouped:
            grouped[code] = {"code": code, "label": code, "items": []}
            order.append(code)
        grouped[code]["items"].append(item)
    return [grouped[c] for c in order]


async def reconstruct_from_legacy(site_dir: Path, redis, sid: str) -> dict:
    """checklist.json 없는 기존 현장을 .md+Redis+zones.json에서 역구성."""
    site_dir = Path(site_dir)

    def _section(md_name: str, redis_key: str, idx_map: dict) -> dict:
        path = site_dir / md_name
        items = parse_numbered(path.read_text(encoding="utf-8")) if path.exists() else []
        return {"categories": _group_by_code(items, idx_map)}

    s_map = await redis.hgetall(f"checklist:{sid}:static:categories")
    d_map = await redis.hgetall(f"checklist:{sid}:dynamic:categories")
    data = {
        "static": _section("static_checklist.md", "static", s_map),
        "dynamic": _section("dynamic_checklist.md", "dynamic", d_map),
        "zones": [],
    }

    zones_path = site_dir / "zones.json"
    if zones_path.exists():
        try:
            raw_zones = json.loads(zones_path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            raw_zones = []
        for z in raw_zones:
            name = z["zone"] if isinstance(z, dict) else z
            safe = name.replace(" ", "_")
            zs_path = site_dir / f"zone_{safe}_static.md"
            zd_path = site_dir / f"zone_{safe}_dynamic.md"
            data["zones"].append({
                "zone": name,
                "static": parse_numbered(zs_path.read_text(encoding="utf-8")) if zs_path.exists() else [],
                "dynamic": parse_numbered(zd_path.read_text(encoding="utf-8")) if zd_path.exists() else [],
            })
    return data


async def load_structured(site_dir: Path, redis, sid: str) -> dict:
    """checklist.json 있으면 읽고, 없으면 레거시 역구성."""
    path = Path(site_dir) / "checklist.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return await reconstruct_from_legacy(site_dir, redis, sid)
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd services/backend && python -m pytest tests/test_checklist_store.py -v`
Expected: PASS (12 passed)

- [ ] **Step 5: 커밋**

```bash
git add services/backend/app/api/checklist_store.py services/backend/tests/test_checklist_store.py
git commit -m "feat(checklist): load_structured + 레거시 역구성"
```

---

## Task 4: 증분 병합 순수 로직 (apply_removes/adds/zone_assignments)

**Files:**
- Modify: `services/backend/app/api/checklist_store.py`
- Test: `services/backend/tests/test_checklist_store.py`

- [ ] **Step 1: 실패하는 테스트 작성** (test 파일 끝에 추가)

```python
from app.api.checklist_store import apply_removes, apply_adds, apply_zone_assignments


def _merge_base():
    return {
        "static": {"categories": [
            {"code": "FIRE", "label": "소방", "items": ["소화기 가렸나?", "통로 막혔나?"]},
        ]},
        "dynamic": {"categories": [{"code": "FALL", "label": "낙상", "items": ["쓰러졌나?"]}]},
        "zones": [{"zone": "정문", "static": ["소화기 가렸나?"], "dynamic": []}],
    }


def test_apply_removes_strips_from_categories_and_zones():
    data = _merge_base()
    apply_removes(data, static_remove=["소화기 가렸나?"], dynamic_remove=[])
    assert data["static"]["categories"][0]["items"] == ["통로 막혔나?"]
    assert data["zones"][0]["static"] == []   # 전 구역에서도 제거


def test_apply_removes_drops_empty_category():
    data = _merge_base()
    apply_removes(data, static_remove=["소화기 가렸나?", "통로 막혔나?"], dynamic_remove=[])
    assert data["static"]["categories"] == []


def test_apply_adds_appends_to_general():
    data = _merge_base()
    apply_adds(data, static_add=["새 항목?"], dynamic_add=[])
    gen = next(c for c in data["static"]["categories"] if c["code"] == "GENERAL")
    assert gen["items"] == ["새 항목?"]
    assert gen["label"] == "일반"


def test_apply_adds_is_idempotent():
    data = _merge_base()
    apply_adds(data, static_add=["통로 막혔나?"], dynamic_add=[])  # 이미 존재
    flat = [i for c in data["static"]["categories"] for i in c["items"]]
    assert flat.count("통로 막혔나?") == 1


def test_apply_zone_assignments_appends_only_new():
    data = _merge_base()
    apply_zone_assignments(data, [{"zone": "정문", "static": ["새 항목?"], "dynamic": []}])
    assert data["zones"][0]["static"] == ["소화기 가렸나?", "새 항목?"]
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd services/backend && python -m pytest tests/test_checklist_store.py -k "apply_" -v`
Expected: FAIL — `ImportError: cannot import name 'apply_removes'`

- [ ] **Step 3: 구현** (checklist_store.py 끝에 추가)

```python
def apply_removes(data: dict, static_remove: list[str], dynamic_remove: list[str]) -> None:
    """수락된 삭제 항목을 공통 카테고리 + 모든 구역에서 제거(in-place). 빈 카테고리는 삭제."""
    for sec, removes in (("static", static_remove), ("dynamic", dynamic_remove)):
        rs = set(removes)
        if not rs:
            continue
        cats = data.get(sec, {}).get("categories", [])
        for cat in cats:
            cat["items"] = [it for it in cat.get("items", []) if it not in rs]
        data[sec]["categories"] = [c for c in cats if c["items"]]
        for zone in data.get("zones", []):
            zone[sec] = [it for it in zone.get(sec, []) if it not in rs]


def apply_adds(data: dict, static_add: list[str], dynamic_add: list[str]) -> None:
    """수락된 추가 항목을 GENERAL 카테고리에 append(in-place, 중복 방지)."""
    for sec, adds in (("static", static_add), ("dynamic", dynamic_add)):
        if not adds:
            continue
        cats = data.setdefault(sec, {}).setdefault("categories", [])
        gen = next((c for c in cats if c.get("code") == "GENERAL"), None)
        if gen is None:
            gen = {"code": "GENERAL", "label": "일반", "items": []}
            cats.append(gen)
        existing = {it for c in cats for it in c.get("items", [])}
        for item in adds:
            if item not in existing:
                gen["items"].append(item)
                existing.add(item)


def apply_zone_assignments(data: dict, zone_subsets: list[dict]) -> None:
    """subset_by_zones 결과(새 항목의 구역 배치)를 기존 구역에 append(in-place, 중복 방지)."""
    by_name = {z["zone"]: z for z in data.get("zones", [])}
    for sub in zone_subsets:
        zone = by_name.get(sub.get("zone"))
        if zone is None:
            continue
        for sec in ("static", "dynamic"):
            existing = set(zone.get(sec, []))
            for item in sub.get(sec, []):
                if item not in existing:
                    zone.setdefault(sec, []).append(item)
                    existing.add(item)
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd services/backend && python -m pytest tests/test_checklist_store.py -v`
Expected: PASS (17 passed)

- [ ] **Step 5: 커밋**

```bash
git add services/backend/app/api/checklist_store.py services/backend/tests/test_checklist_store.py
git commit -m "feat(checklist): 증분 병합 순수 로직(adds/removes/zone)"
```

---

## Task 5: confirm_manual 리팩터 — store.persist로 단일화 (회귀 방지)

**Files:**
- Modify: `services/backend/app/api/manuals.py:365-417` (confirm_manual)
- Modify: `services/backend/app/api/manuals.py:84-111` (`_format_checklist`/`_build_categories_map` 위임)
- Verify: 기존 `tests/test_format_checklist.py`, `tests/test_build_categories_map.py` 그대로 통과

목표: `confirm_manual`이 `.md`/Redis를 직접 쓰던 로직을 제거하고 `checklist_store.persist()`를 호출(=checklist.json도 함께 저장). 파생물 결과는 동일해야 한다. 기존 `_format_checklist`/`_build_categories_map`은 store로 위임해 중복 제거하되 기존 테스트 시그니처는 유지.

- [ ] **Step 1: 기존 헬퍼를 store로 위임** (`manuals.py` 84-111 교체)

```python
from app.api import checklist_store


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
```

- [ ] **Step 2: 기존 헬퍼 테스트 통과 확인**

Run: `cd services/backend && python -m pytest tests/test_format_checklist.py tests/test_build_categories_map.py -v`
Expected: PASS (위임 후에도 동일 결과)

- [ ] **Step 3: confirm_manual을 store.persist 호출로 교체** (`manuals.py` confirm_manual 본문)

```python
@router.post("/confirm")
async def confirm_manual(
    body: ConfirmRequest,
    site_id: str | None = Query(None),
    current_user: User = Depends(require_admin),
) -> dict:
    """확정된 체크리스트를 checklist.json(단일 원본) + 파생물로 저장."""
    sid = _effective_site_id(current_user, site_id)
    if sid is None:
        raise HTTPException(status_code=403, detail="현장을 지정해야 합니다 (superadmin은 site_id 필요).")

    static_cats = [_cat_to_dict(c) for c in body.static_categories]
    dynamic_cats = [_cat_to_dict(c) for c in body.dynamic_categories]
    # categories가 비면 평탄 items를 GENERAL 단일 카테고리로 보존(기존 동작 유지)
    if not static_cats and body.static:
        static_cats = [{"code": "GENERAL", "label": "일반", "items": list(body.static)}]
    if not dynamic_cats and body.dynamic:
        dynamic_cats = [{"code": "GENERAL", "label": "일반", "items": list(body.dynamic)}]

    data = {
        "static": {"categories": static_cats},
        "dynamic": {"categories": dynamic_cats},
        "zones": [{"zone": z.zone, "static": list(z.static), "dynamic": list(z.dynamic)} for z in body.zones],
    }

    await checklist_store.persist(_site_dir(sid), _get_redis(), str(sid), data)

    logger.info("체크리스트 저장 완료: site=%s static=%d dynamic=%d zones=%d",
                sid, len(body.static), len(body.dynamic), len(body.zones))
    return {"status": "saved", "static_count": len(body.static), "dynamic_count": len(body.dynamic)}
```

> 주의: 기존 confirm은 categories가 비면 .md만 쓰고 Redis 맵은 비웠다. 위 코드는 비어도 GENERAL로 채워 Redis 맵을 쓴다 — 인퍼런스는 맵이 없으면 GENERAL로 처리하므로 결과 동일(코드 태그 동작 동일). `.md` 번호 텍스트는 100% 동일.

- [ ] **Step 4: 전체 백엔드 테스트 통과 확인**

Run: `cd services/backend && python -m pytest tests/ -v`
Expected: PASS (기존 + 신규 store 테스트 모두 green)

- [ ] **Step 5: 커밋**

```bash
git add services/backend/app/api/manuals.py
git commit -m "refactor(manuals): confirm을 checklist_store.persist로 단일화"
```

---

## Task 6: F1 편집 엔드포인트 (GET/PUT checklist/full)

**Files:**
- Modify: `services/backend/app/api/manuals.py` (스키마 + 2개 엔드포인트 추가)

- [ ] **Step 1: 스키마 추가** (`manuals.py` ConfirmRequest 아래)

```python
class ChecklistSection(BaseModel):
    categories: list[CategoryItem] = []


class ChecklistFull(BaseModel):
    static: ChecklistSection = ChecklistSection()
    dynamic: ChecklistSection = ChecklistSection()
    zones: list[ZoneChecklist] = []
```

- [ ] **Step 2: GET /checklist/full 추가** (`manuals.py`)

```python
@router.get("/checklist/full")
async def get_checklist_full(
    site_id: str | None = Query(None),
    current_user: User = Depends(get_current_user),
) -> dict:
    """편집용 구조화 체크리스트(JSON 원본). 없으면 레거시에서 역구성."""
    sid = _effective_site_id(current_user, site_id)
    if sid is None:
        return {"static": {"categories": []}, "dynamic": {"categories": []}, "zones": []}
    return await checklist_store.load_structured(_site_dir(sid), _get_redis(), str(sid))
```

- [ ] **Step 3: PUT /checklist 추가** (`manuals.py`)

```python
@router.put("/checklist")
async def update_checklist_full(
    body: ChecklistFull,
    site_id: str | None = Query(None),
    current_user: User = Depends(require_admin),
) -> dict:
    """편집된 구조화 체크리스트 저장(공통+구역). 빈 문자열 항목은 제거."""
    sid = _effective_site_id(current_user, site_id)
    if sid is None:
        raise HTTPException(status_code=403, detail="현장을 지정해야 합니다 (superadmin은 site_id 필요).")

    def _clean_cats(cats):
        out = []
        for c in cats:
            items = [i.strip() for i in c.items if i and i.strip()]
            if items:
                out.append({"code": (c.code or "GENERAL").strip(), "label": c.label or c.code, "items": items})
        return out

    data = {
        "static": {"categories": _clean_cats(body.static.categories)},
        "dynamic": {"categories": _clean_cats(body.dynamic.categories)},
        "zones": [
            {"zone": z.zone,
             "static": [i.strip() for i in z.static if i and i.strip()],
             "dynamic": [i.strip() for i in z.dynamic if i and i.strip()]}
            for z in body.zones
        ],
    }
    await checklist_store.persist(_site_dir(sid), _get_redis(), str(sid), data)
    return {"status": "saved"}
```

- [ ] **Step 4: 임포트 가능 확인 (스모크)**

Run: `cd services/backend && python -c "import app.api.manuals"`
Expected: 출력 없음(에러 없이 import 성공)

- [ ] **Step 5: 커밋**

```bash
git add services/backend/app/api/manuals.py
git commit -m "feat(manuals): F1 구조화 체크리스트 GET/PUT 엔드포인트"
```

---

## Task 7: diff_checklist 에이전트

**Files:**
- Modify: `services/backend/app/api/agent/checklist_agent.py` (함수 추가)
- Test: `services/backend/tests/test_diff_checklist.py`

- [ ] **Step 1: 실패하는 테스트 작성**

`services/backend/tests/test_diff_checklist.py`:
```python
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _mock_resp(added, removed):
    resp = MagicMock()
    resp.choices[0].message.content = json.dumps(
        {"added": added, "removed_candidates": removed}, ensure_ascii=False
    )
    return resp


@pytest.mark.asyncio
async def test_diff_no_existing_returns_all_as_added():
    """기존 항목이 없으면 LLM 호출 없이 전부 added."""
    from app.api.agent.checklist_agent import diff_checklist
    result = await diff_checklist([], ["새1?", "새2?"])
    assert result == {"added": ["새1?", "새2?"], "removed_candidates": []}


@pytest.mark.asyncio
async def test_diff_no_new_returns_all_as_removed():
    """새 항목이 없으면 LLM 호출 없이 전부 removed_candidates."""
    from app.api.agent.checklist_agent import diff_checklist
    result = await diff_checklist(["기존1?"], [])
    assert result == {"added": [], "removed_candidates": ["기존1?"]}


@pytest.mark.asyncio
async def test_diff_semantic_split():
    """LLM이 added/removed_candidates로 분류한 결과를 그대로 반환."""
    mock = _mock_resp(added=["신규 항목?"], removed=["폐기된 항목?"])
    with patch("app.api.agent.checklist_agent._get_openai") as mock_get:
        client = MagicMock()
        client.chat.completions.create = AsyncMock(return_value=mock)
        mock_get.return_value = client
        from app.api.agent.checklist_agent import diff_checklist
        result = await diff_checklist(["폐기된 항목?", "유지 항목?"], ["유지 항목?", "신규 항목?"])
    assert result["added"] == ["신규 항목?"]
    assert result["removed_candidates"] == ["폐기된 항목?"]


@pytest.mark.asyncio
async def test_diff_empty_response_falls_back_to_set_diff():
    """LLM 빈 응답 시 단순 집합 차집합으로 fallback."""
    resp = MagicMock()
    resp.choices[0].message.content = ""
    with patch("app.api.agent.checklist_agent._get_openai") as mock_get:
        client = MagicMock()
        client.chat.completions.create = AsyncMock(return_value=resp)
        mock_get.return_value = client
        from app.api.agent.checklist_agent import diff_checklist
        result = await diff_checklist(["a?"], ["a?", "b?"])
    assert result["added"] == ["b?"]
    assert result["removed_candidates"] == []
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd services/backend && python -m pytest tests/test_diff_checklist.py -v`
Expected: FAIL — `ImportError: cannot import name 'diff_checklist'`

- [ ] **Step 3: 구현** (`checklist_agent.py` 끝에 추가)

```python
_DIFF_SYSTEM = (
    "두 개의 CCTV 안전 체크리스트 항목 리스트가 주어진다: 'existing'(기존)과 'new'(새 문서에서 추출).\n"
    "의미 기준으로 비교하라.\n\n"
    "[규칙]\n"
    "- added: new에만 있고 existing에는 의미상 없는 항목. 반드시 new의 원문 그대로 사용.\n"
    "- removed_candidates: existing에만 있고 new에는 의미상 사라진 항목. 반드시 existing의 원문 그대로 사용.\n"
    "- 문구만 다르고 의미가 같으면 동일 항목으로 보고 added/removed 어디에도 넣지 마라.\n"
    "- 원문을 절대 수정하지 마라.\n\n"
    '{"added": ["..."], "removed_candidates": ["..."]} 형태 JSON으로만 출력하라.'
)


async def diff_checklist(existing_items: list[str], new_items: list[str]) -> dict:
    """기존 vs 새 항목 리스트를 의미 기반 비교해 {added, removed_candidates} 반환.

    한쪽이 비면 LLM 호출 없이 즉시 반환. LLM 실패/빈 응답 시 단순 집합 차집합 fallback.
    """
    if not existing_items:
        return {"added": list(new_items), "removed_candidates": []}
    if not new_items:
        return {"added": [], "removed_candidates": list(existing_items)}

    def _set_fallback() -> dict:
        ex = set(existing_items)
        nw = set(new_items)
        return {
            "added": [i for i in new_items if i not in ex],
            "removed_candidates": [i for i in existing_items if i not in nw],
        }

    messages = [
        {"role": "system", "content": _DIFF_SYSTEM},
        {"role": "user", "content": json.dumps(
            {"existing": existing_items, "new": new_items}, ensure_ascii=False)},
    ]
    try:
        resp = await _get_openai().chat.completions.create(
            model=_MODEL, messages=messages, response_format={"type": "json_object"},
        )
        raw = resp.choices[0].message.content or ""
        if not raw:
            return _set_fallback()
        data = json.loads(raw)
        return {
            "added": data.get("added", []),
            "removed_candidates": data.get("removed_candidates", []),
        }
    except Exception as e:
        logger.warning("diff_checklist 실패, 집합 차집합 fallback: %s", e)
        return _set_fallback()
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd services/backend && python -m pytest tests/test_diff_checklist.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: 커밋**

```bash
git add services/backend/app/api/agent/checklist_agent.py services/backend/tests/test_diff_checklist.py
git commit -m "feat(agent): diff_checklist — 의미 기반 추가/삭제후보 diff"
```

---

## Task 8: F2 엔드포인트 (analyze-diff / merge)

**Files:**
- Modify: `services/backend/app/api/manuals.py` (스키마 + 2개 엔드포인트, import 추가)

- [ ] **Step 1: import + 스키마 추가** (`manuals.py`)

상단 import에 `diff_checklist` 추가:
```python
from app.api.agent.checklist_agent import analyze_pdf, refine_checklist, subset_by_zones, normalize_categories, diff_checklist
```

스키마 추가(ChecklistFull 아래):
```python
class MergeRequest(BaseModel):
    static_add: list[str] = []
    static_remove: list[str] = []
    dynamic_add: list[str] = []
    dynamic_remove: list[str] = []
```

- [ ] **Step 2: POST /analyze-diff 추가** (`manuals.py`)

```python
@router.post("/analyze-diff")
async def analyze_diff(
    file: UploadFile = File(...),
    site_id: str | None = Query(None),
    current_user: User = Depends(require_admin),
) -> dict:
    """새 PDF를 분석해 기존 확정 체크리스트와 비교한 추가/삭제후보 반환."""
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
```

- [ ] **Step 3: POST /merge 추가** (`manuals.py`)

```python
@router.post("/merge")
async def merge_checklist(
    body: MergeRequest,
    site_id: str | None = Query(None),
    current_user: User = Depends(require_admin),
) -> dict:
    """수락된 추가/삭제를 기존 체크리스트에 병합. 추가 항목은 구역 자동 배치."""
    sid = _effective_site_id(current_user, site_id)
    if sid is None:
        raise HTTPException(status_code=403, detail="현장을 지정해야 합니다 (superadmin은 site_id 필요).")

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
```

- [ ] **Step 4: import 스모크 + 전체 테스트**

Run: `cd services/backend && python -c "import app.api.manuals" && python -m pytest tests/ -v`
Expected: import 성공 + 전체 PASS

- [ ] **Step 5: 커밋**

```bash
git add services/backend/app/api/manuals.py
git commit -m "feat(manuals): F2 analyze-diff + merge 엔드포인트"
```

---

## Task 9: 프론트 API 함수 추가

**Files:**
- Modify: `services/frontend/src/api/manuals.js`

- [ ] **Step 1: 4개 함수 추가** (`manuals.js`, `fetchChecklist` 아래)

```javascript
export async function fetchChecklistFull(siteId = null) {
  if (DUMMY_MODE) return { static: { categories: [] }, dynamic: { categories: [] }, zones: [] }
  const q = siteId ? `?site_id=${encodeURIComponent(siteId)}` : ''
  return api.get(`/manuals/checklist/full${q}`).then(r => r.data)
}

export async function saveChecklistFull(data, siteId = null) {
  if (DUMMY_MODE) return { status: 'saved' }
  return api.put(`/manuals/checklist${_siteQuery(siteId)}`, data).then(r => r.data)
}

export async function analyzeDiff(file, siteId = null) {
  if (DUMMY_MODE) {
    return {
      static: { added: ['새로 추가된 static 항목?'], removed_candidates: [] },
      dynamic: { added: [], removed_candidates: ['사라진 dynamic 항목?'] },
    }
  }
  const form = new FormData()
  form.append('file', file)
  return api.post(`/manuals/analyze-diff${_siteQuery(siteId)}`, form, { timeout: 120000 }).then(r => r.data)
}

export async function mergeChecklist(payload, siteId = null) {
  if (DUMMY_MODE) return { status: 'merged' }
  return api.post(`/manuals/merge${_siteQuery(siteId)}`, payload).then(r => r.data)
}
```

- [ ] **Step 2: 빌드 스모크**

Run: `cd services/frontend && npx vite build 2>&1 | tail -5`
Expected: `built in ...` (에러 없음)

- [ ] **Step 3: 커밋**

```bash
git add services/frontend/src/api/manuals.js
git commit -m "feat(frontend): 체크리스트 편집/증분 API 함수"
```

---

## Task 10: F1 편집 UI — ChecklistEditor 컴포넌트 + ManualView 통합

**Files:**
- Create: `services/frontend/src/components/manual/ChecklistEditor.vue`
- Modify: `services/frontend/src/views/ManualView.vue` (확정 체크리스트 read-only 영역 → 편집기)

- [ ] **Step 1: ChecklistEditor.vue 작성**

`services/frontend/src/components/manual/ChecklistEditor.vue`:
```vue
<template>
  <div class="space-y-5">
    <!-- 공통 static/dynamic -->
    <div v-for="sec in ['static', 'dynamic']" :key="sec">
      <h4 class="text-xs font-semibold mb-2" style="color: var(--text-muted);">
        {{ sec === 'static' ? '정적(스냅샷)' : '동적(행동)' }} 체크리스트
      </h4>
      <div v-for="(cat, ci) in model[sec].categories" :key="ci" class="mb-3">
        <div class="flex items-center gap-2 mb-1">
          <span class="text-[10px] font-bold px-1.5 py-0.5 rounded"
                style="background: var(--bg-elevated); color: var(--text-muted);">{{ cat.code }}</span>
          <span class="text-xs" style="color: var(--text-subtle);">{{ cat.label }}</span>
        </div>
        <div v-for="(item, ii) in cat.items" :key="ii" class="flex items-center gap-2 mb-1.5">
          <input v-model="cat.items[ii]"
                 class="app-input flex-1 px-3 py-1.5 rounded-lg text-xs"
                 style="background: var(--bg-elevated); border: 1px solid var(--border); color: var(--text-primary);" />
          <button @click="cat.items.splice(ii, 1)" class="text-xs px-2 py-1 rounded"
                  style="color: var(--red);">삭제</button>
        </div>
        <button @click="cat.items.push('')" class="text-xs mt-1" style="color: var(--blue);">+ 항목 추가</button>
      </div>
      <button @click="addCategory(sec)" class="text-xs mt-1" style="color: var(--text-muted);">+ 카테고리</button>
    </div>

    <!-- 구역별 -->
    <div v-if="model.zones.length">
      <h4 class="text-xs font-semibold mb-2" style="color: var(--text-muted);">구역별 체크리스트</h4>
      <div v-for="(zone, zi) in model.zones" :key="zi" class="rounded-xl p-3 mb-2"
           style="background: var(--bg-card); border: 1px solid var(--border);">
        <p class="text-sm font-semibold mb-2" style="color: var(--text-primary);">{{ zone.zone }}</p>
        <div v-for="sec in ['static', 'dynamic']" :key="sec" class="mb-2">
          <p class="text-[10px] mb-1" style="color: var(--text-subtle);">{{ sec === 'static' ? '정적' : '동적' }}</p>
          <div v-for="(item, ii) in zone[sec]" :key="ii" class="flex items-center gap-2 mb-1">
            <input v-model="zone[sec][ii]"
                   class="flex-1 px-3 py-1.5 rounded-lg text-xs"
                   style="background: var(--bg-elevated); border: 1px solid var(--border); color: var(--text-primary);" />
            <button @click="zone[sec].splice(ii, 1)" class="text-xs px-2 py-1 rounded" style="color: var(--red);">삭제</button>
          </div>
          <button @click="zone[sec].push('')" class="text-xs" style="color: var(--blue);">+ 항목</button>
        </div>
      </div>
    </div>

    <div class="flex gap-2 pt-2">
      <button @click="$emit('save', model)" :disabled="saving"
              class="px-4 py-2 rounded-xl text-sm font-semibold"
              style="background: #2563eb; color: white;">{{ saving ? '저장 중...' : '저장' }}</button>
      <button @click="reset" class="px-4 py-2 rounded-xl text-sm"
              style="background: var(--bg-elevated); color: var(--text-muted); border: 1px solid var(--border);">취소</button>
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'

const props = defineProps({
  value: { type: Object, required: true },   // {static:{categories},dynamic:{categories},zones}
  saving: { type: Boolean, default: false },
})
defineEmits(['save'])

function clone(v) { return JSON.parse(JSON.stringify(v)) }
const model = ref(normalize(props.value))

function normalize(v) {
  return {
    static: { categories: v?.static?.categories ?? [] },
    dynamic: { categories: v?.dynamic?.categories ?? [] },
    zones: (v?.zones ?? []).map(z => ({ zone: z.zone, static: z.static ?? [], dynamic: z.dynamic ?? [] })),
  }
}
function reset() { model.value = normalize(props.value) }
function addCategory(sec) {
  model.value[sec].categories.push({ code: 'GENERAL', label: '일반', items: [''] })
}
watch(() => props.value, (v) => { model.value = normalize(clone(v)) })
</script>
```

- [ ] **Step 2: ManualView에 편집기 통합**

`services/frontend/src/views/ManualView.vue` — 확정 체크리스트를 보여주던 read-only `<pre>` 영역(`confirmedChecklist.static/dynamic` 출력부, 약 219-224행)을 다음으로 교체. 편집 토글 버튼 + ChecklistEditor:
```vue
<div v-if="canManage" class="mt-4">
  <div class="flex items-center justify-between mb-3">
    <h3 class="font-semibold text-sm" style="color: var(--text-primary);">확정 체크리스트</h3>
    <button @click="toggleEdit" class="text-xs px-3 py-1.5 rounded-lg"
            style="background: var(--bg-elevated); color: var(--text-muted); border: 1px solid var(--border);">
      {{ editing ? '편집 닫기' : '편집' }}
    </button>
  </div>
  <ChecklistEditor v-if="editing" :value="fullChecklist" :saving="savingFull" @save="onSaveFull" />
  <template v-else>
    <pre v-if="confirmedChecklist.static" class="text-xs whitespace-pre-wrap leading-relaxed" style="color: var(--text-muted);">{{ confirmedChecklist.static }}</pre>
    <pre v-if="confirmedChecklist.dynamic" class="text-xs whitespace-pre-wrap leading-relaxed mt-2" style="color: var(--text-muted);">{{ confirmedChecklist.dynamic }}</pre>
  </template>
  <p v-if="fullSaved" class="text-xs mt-2" style="color: var(--green);">저장되었습니다.</p>
</div>
```

script `<script setup>`에 추가(기존 import 줄에 함수 추가):
```javascript
import ChecklistEditor from '../components/manual/ChecklistEditor.vue'
import { fetchChecklistFull, saveChecklistFull } from '../api/manuals.js'

const editing = ref(false)
const fullChecklist = ref({ static: { categories: [] }, dynamic: { categories: [] }, zones: [] })
const savingFull = ref(false)
const fullSaved = ref(false)

async function toggleEdit() {
  editing.value = !editing.value
  if (editing.value) {
    fullChecklist.value = await fetchChecklistFull(manageSiteId.value)
  }
}
async function onSaveFull(data) {
  savingFull.value = true
  fullSaved.value = false
  try {
    await saveChecklistFull(data, manageSiteId.value)
    fullSaved.value = true
    editing.value = false
    await loadConfirmedView()   // 기존 read-only 뷰 갱신 함수 재사용
  } finally {
    savingFull.value = false
  }
}
```

> `manageSiteId`, `loadConfirmedView`, `canManage`는 ManualView에 이미 존재. 없으면 기존 패턴대로 정의.

- [ ] **Step 3: 빌드 + 컨테이너 재기동 후 수동 검증**

Run: `cd services/frontend && npx vite build 2>&1 | tail -3`
Expected: 빌드 성공.

Run: `cd infra && docker compose build frontend && docker compose up -d --force-recreate frontend`

수동 검증(브라우저 하드 리프레시):
1. admin으로 로그인 → 메뉴얼 페이지 → "편집" 클릭 → 확정 체크리스트가 편집 폼으로 열림.
2. 항목 수정/삭제/추가, 구역 항목 수정 → "저장" → "저장되었습니다" → read-only 뷰 갱신 확인.
3. viewer 계정은 "편집" 버튼 안 보임(canManage=false).

- [ ] **Step 4: 커밋**

```bash
git add services/frontend/src/components/manual/ChecklistEditor.vue services/frontend/src/views/ManualView.vue
git commit -m "feat(frontend): F1 확정 체크리스트 직접 편집 UI"
```

---

## Task 11: F2 UI — 업로드 모드 선택 + DiffReview

**Files:**
- Create: `services/frontend/src/components/manual/DiffReview.vue`
- Modify: `services/frontend/src/views/ManualView.vue` (PDF 업로드 시 모드 선택 + diff 리뷰)

- [ ] **Step 1: DiffReview.vue 작성**

`services/frontend/src/components/manual/DiffReview.vue`:
```vue
<template>
  <div class="space-y-4">
    <div v-for="sec in ['static', 'dynamic']" :key="sec">
      <h4 class="text-xs font-semibold mb-2" style="color: var(--text-muted);">
        {{ sec === 'static' ? '정적' : '동적' }}
      </h4>
      <div v-if="diff[sec].added.length" class="mb-2">
        <p class="text-[11px] mb-1" style="color: var(--green);">추가 ({{ selectedAdd[sec].length }}/{{ diff[sec].added.length }})</p>
        <label v-for="(item, i) in diff[sec].added" :key="'a' + i" class="flex items-center gap-2 mb-1 text-xs" style="color: var(--text-primary);">
          <input type="checkbox" :value="item" v-model="selectedAdd[sec]" />
          <span>{{ item }}</span>
        </label>
      </div>
      <div v-if="diff[sec].removed_candidates.length" class="mb-2">
        <p class="text-[11px] mb-1" style="color: var(--red);">삭제 후보 ({{ selectedRemove[sec].length }}/{{ diff[sec].removed_candidates.length }})</p>
        <label v-for="(item, i) in diff[sec].removed_candidates" :key="'r' + i" class="flex items-center gap-2 mb-1 text-xs" style="color: var(--text-muted);">
          <input type="checkbox" :value="item" v-model="selectedRemove[sec]" />
          <span class="line-through">{{ item }}</span>
        </label>
      </div>
      <p v-if="!diff[sec].added.length && !diff[sec].removed_candidates.length" class="text-xs" style="color: var(--text-subtle);">변경 없음</p>
    </div>
    <div class="flex gap-2 pt-1">
      <button @click="emitMerge" :disabled="merging" class="px-4 py-2 rounded-xl text-sm font-semibold" style="background: #2563eb; color: white;">
        {{ merging ? '병합 중...' : '병합' }}
      </button>
      <button @click="$emit('cancel')" class="px-4 py-2 rounded-xl text-sm" style="background: var(--bg-elevated); color: var(--text-muted); border: 1px solid var(--border);">취소</button>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const props = defineProps({
  diff: { type: Object, required: true },   // {static:{added,removed_candidates}, dynamic:{...}}
  merging: { type: Boolean, default: false },
})
const emit = defineEmits(['merge', 'cancel'])

// 기본값: 추가=전체 체크, 삭제=해제
const selectedAdd = ref({ static: [...props.diff.static.added], dynamic: [...props.diff.dynamic.added] })
const selectedRemove = ref({ static: [], dynamic: [] })

function emitMerge() {
  emit('merge', {
    static_add: selectedAdd.value.static,
    dynamic_add: selectedAdd.value.dynamic,
    static_remove: selectedRemove.value.static,
    dynamic_remove: selectedRemove.value.dynamic,
  })
}
</script>
```

- [ ] **Step 2: ManualView — 업로드 시 모드 선택 + diff 흐름**

`ManualView.vue`의 PDF "분석" 버튼 영역에 모드 분기 추가. 기존 `onAnalyze`는 전체 재생성으로 유지하고, 기존 확정 체크리스트 존재 시 "증분 병합" 버튼을 함께 노출:
```vue
<div v-if="docFile" class="flex gap-2 mb-3">
  <button @click="onAnalyze" :disabled="checklist.loading"
          class="px-4 py-2 rounded-xl text-sm font-semibold" style="background: #2563eb; color: white;">
    전체 재생성
  </button>
  <button v-if="hasExistingChecklist" @click="onAnalyzeDiff" :disabled="diffState.loading"
          class="px-4 py-2 rounded-xl text-sm font-semibold"
          style="background: var(--bg-elevated); color: var(--text-primary); border: 1px solid var(--border);">
    {{ diffState.loading ? '비교 중...' : '증분 병합' }}
  </button>
</div>

<div v-if="diffState.diff" class="rounded-xl p-4 mb-6" style="background: var(--bg-card); border: 1px solid var(--border);">
  <DiffReview :diff="diffState.diff" :merging="diffState.merging" @merge="onMerge" @cancel="diffState.diff = null" />
</div>
```

script 추가:
```javascript
import DiffReview from '../components/manual/DiffReview.vue'
import { analyzeDiff, mergeChecklist } from '../api/manuals.js'

const diffState = reactive({ loading: false, merging: false, diff: null })
const hasExistingChecklist = computed(() => !!(confirmedChecklist.static || confirmedChecklist.dynamic))

async function onAnalyzeDiff() {
  diffState.loading = true
  diffState.diff = null
  try {
    diffState.diff = await analyzeDiff(docFile.value, manageSiteId.value)
  } catch (e) {
    uploadError.value = e.response?.data?.detail ?? e.message
  } finally {
    diffState.loading = false
  }
}
async function onMerge(payload) {
  diffState.merging = true
  try {
    await mergeChecklist(payload, manageSiteId.value)
    diffState.diff = null
    await loadConfirmedView()
  } finally {
    diffState.merging = false
  }
}
```

> `docFile`, `confirmedChecklist`, `uploadError`, `manageSiteId`, `loadConfirmedView`는 ManualView에 이미 존재. `reactive`, `computed`가 import 안 돼 있으면 추가.

- [ ] **Step 3: 빌드 + 재기동 + 수동 검증**

Run: `cd services/frontend && npx vite build 2>&1 | tail -3` → 성공
Run: `cd infra && docker compose build frontend && docker compose up -d --force-recreate frontend`

수동 검증:
1. 기존 체크리스트가 있는 현장에서 새 PDF 업로드 → "전체 재생성" / "증분 병합" 버튼 둘 다 노출.
2. "증분 병합" → 추가(기본 체크)/삭제후보(기본 해제) 리스트 표시 → "병합" → 확정 체크리스트 갱신.
3. 체크리스트 없는 현장은 "증분 병합" 버튼 미노출(전체 재생성만).

- [ ] **Step 4: 커밋**

```bash
git add services/frontend/src/components/manual/DiffReview.vue services/frontend/src/views/ManualView.vue
git commit -m "feat(frontend): F2 증분 병합 모드 선택 + diff 리뷰 UI"
```

---

## Task 12: 통합 검증 (회귀 + E2E 스모크)

**Files:** 없음 (검증 전용)

- [ ] **Step 1: 백엔드 전체 테스트**

Run: `cd services/backend && python -m pytest tests/ -v`
Expected: 전체 PASS (신규 store/diff 포함, 기존 회귀 없음)

- [ ] **Step 2: 백엔드 재빌드 + 기동**

Run: `cd infra && docker compose build backend && docker compose up -d --force-recreate backend`
Run: `docker compose logs --tail=30 backend` → 기동 에러 없음 확인.

- [ ] **Step 3: 파생물 동일성(회귀) 확인 — confirm 후 .md/Redis**

admin으로 PDF 분석→confirm 1회 수행 후:
Run: `docker compose exec backend sh -c "ls /app/prompts/<site_id>/ && cat /app/prompts/<site_id>/static_checklist.md"`
Expected: `checklist.json` 신규 존재 + `static_checklist.md`가 기존과 동일한 `N. 항목?` 번호 형식.
Run: `docker compose exec redis redis-cli HGETALL "checklist:<site_id>:static:categories"`
Expected: index→code 맵 정상.

- [ ] **Step 4: 인퍼런스 회귀 확인**

Run: `docker compose logs --tail=50 inference 2>/dev/null | grep -i "checklist\|error" | tail -20`
Expected: 체크리스트 로딩 정상, 신규 에러 없음(파일/Redis 포맷 불변).

- [ ] **Step 5: 최종 커밋(있으면) + 요약**

```bash
git status
git log --oneline dev1..dev2 | cat
```
Expected: dev2에 Task 1~11 커밋들이 순서대로 쌓여 있음.

---

## Self-Review (작성자 점검)

**1. 스펙 커버리지:**
- 섹션1 데이터모델 → Task 1·2·3 (store/persist/load) ✅
- 섹션2 F1 백엔드 → Task 6 (GET/PUT) ✅
- 섹션3 F1 프론트 → Task 10 ✅
- 섹션4 F2 에이전트 diff → Task 7 ✅
- 섹션5 F2 병합+자동구역 → Task 4(순수) + Task 8(엔드포인트) ✅
- 섹션6 F2 프론트 → Task 11 ✅
- 섹션7 테스트 → 각 백엔드 Task에 단위테스트 포함 + Task 12 통합 ✅
- confirm 회귀 방지 → Task 5 ✅

**2. 플레이스홀더:** 없음(모든 코드 step에 완전한 코드 포함).

**3. 타입 일관성:** 구조화 JSON 형태(`{static:{categories},dynamic:{categories},zones:[{zone,static,dynamic}]}`)가 store/엔드포인트/프론트에서 일관. `categories_map`/`items_map`/`item_to_code` 시그니처가 persist/load에서 일치. `diff_checklist(existing, new)` 반환 `{added, removed_candidates}`가 analyze-diff/DiffReview에서 일치. `MergeRequest` 필드(`static_add/static_remove/dynamic_add/dynamic_remove`)가 merge 엔드포인트/DiffReview emit에서 일치.

**비목표(YAGNI):** 버전 히스토리, 수정 의미매칭, DB 이전, 협업편집 — 미포함.
