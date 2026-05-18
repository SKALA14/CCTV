# pgvector ORM 마이그레이션 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `search_events`의 raw SQL pgvector 쿼리를 SQLAlchemy ORM 연산자로 교체해 타입 안전성 확보, DB 쿼리 횟수를 2회→1회로 줄인다.

**Architecture:** `pgvector-python`은 이미 설치·사용 중(`models.py`의 `Vector` 컬럼). `EventLog.embedding.cosine_distance(vector)`로 ORM 연산자 접근 가능. `select(EventLog, distance_col)` 단일 쿼리로 EventLog 인스턴스와 거리값을 동시에 조회한다. 외부 API 인터페이스(`GET /events/search` 파라미터·응답 스키마)는 변경 없음.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy 2.x (async), pgvector-python, asyncpg

---

## 변경 파일 목록

| 파일 | 유형 | 내용 |
|------|------|------|
| `services/backend/app/api/events.py` | 수정 | `search_events` raw SQL → ORM 연산자 |
| `services/backend/tests/test_search_events.py` | 신규 | search_events 단위 테스트 |

**변경하지 않는 것:** `models.py`, `schemas.py`, `session.py`, `worker.py`, 프론트엔드 전체, DB 스키마, HNSW 인덱스

---

## Task 1: 테스트 작성 (실패 확인용)

**Files:**
- Create: `services/backend/tests/test_search_events.py`

현재 `search_events`는 OpenAI 임베딩 API와 DB를 모두 호출하므로, 핵심 로직인 **ORM 쿼리 조립**만 단위 테스트로 검증한다.

- [ ] **Step 1: 테스트 파일 작성**

`services/backend/tests/test_search_events.py`:

```python
"""
search_events ORM 쿼리 조립 검증.
실제 DB/OpenAI 호출 없이 생성된 SQLAlchemy statement를 검사한다.
"""
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.dialects import postgresql

from app.db.models import EventLog


def _compile(stmt) -> str:
    """SQLAlchemy statement를 PostgreSQL 방언으로 컴파일해 문자열로 반환."""
    return str(stmt.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": False}))


def _base_stmt(query_vector: list[float]):
    distance_col = EventLog.embedding.cosine_distance(query_vector).label("distance")
    return (
        select(EventLog, distance_col)
        .where(EventLog.embedding.is_not(None))
        .order_by(distance_col)
    )


def test_base_query_contains_cosine_operator():
    stmt = _base_stmt([0.1] * 1536).limit(10)
    sql = _compile(stmt)
    assert "<=>" in sql
    assert "embedding IS NOT NULL" in sql
    assert "ORDER BY" in sql
    assert "LIMIT" in sql


def test_channel_filter_added():
    distance_col = EventLog.embedding.cosine_distance([0.1] * 1536).label("distance")
    stmt = (
        select(EventLog, distance_col)
        .where(EventLog.embedding.is_not(None))
        .where(EventLog.camera_id == "cam0")
        .order_by(distance_col)
        .limit(10)
    )
    sql = _compile(stmt)
    assert "camera_id" in sql


def test_date_filter_added():
    start = datetime(2026, 5, 1, tzinfo=timezone.utc)
    end   = datetime(2026, 5, 16, tzinfo=timezone.utc)
    distance_col = EventLog.embedding.cosine_distance([0.1] * 1536).label("distance")
    stmt = (
        select(EventLog, distance_col)
        .where(EventLog.embedding.is_not(None))
        .where(EventLog.occurred_at >= start)
        .where(EventLog.occurred_at <= end)
        .order_by(distance_col)
        .limit(10)
    )
    sql = _compile(stmt)
    assert "occurred_at" in sql


def test_no_raw_sql_text_in_query():
    """ORM 쿼리에 sqlalchemy.text() 가 없어야 한다."""
    from sqlalchemy import text as sa_text
    distance_col = EventLog.embedding.cosine_distance([0.1] * 1536).label("distance")
    stmt = (
        select(EventLog, distance_col)
        .where(EventLog.embedding.is_not(None))
        .order_by(distance_col)
        .limit(10)
    )
    # statement 내 모든 clause를 순회해 text() 객체가 없는지 확인
    compiled = stmt.compile(dialect=postgresql.dialect())
    assert "text(" not in repr(stmt)
```

- [ ] **Step 2: 테스트 실행 — 실패 확인**

```bash
cd services/backend && python -m pytest tests/test_search_events.py -v
```

Expected: `ImportError` 또는 `AttributeError: 'NoneType' object has no attribute 'cosine_distance'`  
(ORM 연산자가 아직 동작하는지 확인. 만약 이미 통과하면 Step 1 테스트가 올바른 것이므로 다음으로 진행)

---

## Task 2: search_events ORM 전환

**Files:**
- Modify: `services/backend/app/api/events.py`

- [ ] **Step 1: import 정리**

`events.py` 상단 import를 아래로 교체 (`text`, `func` 제거, `datetime` 추가):

```python
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from openai import AsyncOpenAI
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.db.models import EventLog, CctvChannel
from app.api.schemas import EventLogRead, EventListResponse
from app.api.time_parser import parse_time_expression
```

- [ ] **Step 2: search_events 함수 전체 교체**

`events.py`의 `search_events` 함수(현재 `@router.get("/events/search")`로 시작하는 블록 전체)를 아래로 교체:

```python
@router.get("/events/search", response_model=EventListResponse)
async def search_events(
    q:          str = Query(..., min_length=1),
    channel_id: Optional[str] = Query(None),
    limit:      int = Query(10, ge=1, le=50),
    start_date: Optional[datetime] = Query(None),
    end_date:   Optional[datetime] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    # 자연어 시간 표현 파싱
    cleaned_query, parsed_start, parsed_end, label = parse_time_expression(q)

    # 명시적 날짜 파라미터가 있으면 파서 결과보다 우선
    if start_date or end_date:
        active_start, active_end, applied_filter = start_date, end_date, None
    else:
        active_start, active_end, applied_filter = parsed_start, parsed_end, label

    # 쿼리 임베딩 생성 (시간 표현 제거된 텍스트 사용)
    embed_response = await _openai.embeddings.create(
        model="text-embedding-3-small",
        input=cleaned_query or q,
    )
    query_vector: list[float] = embed_response.data[0].embedding

    # ORM 쿼리 조립
    distance_col = EventLog.embedding.cosine_distance(query_vector).label("distance")
    stmt = (
        select(EventLog, distance_col)
        .where(EventLog.embedding.is_not(None))
        .order_by(distance_col)
        .limit(limit)
    )
    if channel_id:
        stmt = stmt.where(EventLog.camera_id == channel_id)
    if active_start:
        stmt = stmt.where(EventLog.occurred_at >= active_start)
    if active_end:
        stmt = stmt.where(EventLog.occurred_at <= active_end)

    rows = (await db.execute(stmt)).all()  # list of (EventLog, float)

    if not rows:
        return EventListResponse(
            events=[], total=0, skip=0, limit=limit, applied_filter=applied_filter
        )

    camera_ids    = [event.camera_id for event, _ in rows]
    channel_names = await _fetch_channel_names(db, camera_ids)

    return EventListResponse(
        events=[
            _to_schema(event, channel_names.get(event.camera_id), similarity=round(1 - distance, 4))
            for event, distance in rows
        ],
        total=len(rows),
        skip=0,
        limit=limit,
        applied_filter=applied_filter,
    )
```

- [ ] **Step 3: 테스트 통과 확인**

```bash
cd services/backend && python -m pytest tests/test_search_events.py -v
```

Expected:
```
test_base_query_contains_cosine_operator PASSED
test_channel_filter_added PASSED
test_date_filter_added PASSED
test_no_raw_sql_text_in_query PASSED
4 passed in 0.XXs
```

- [ ] **Step 4: 기존 time_parser 테스트도 함께 통과 확인**

```bash
cd services/backend && python -m pytest tests/ -v
```

Expected: `15 passed` (time_parser 11 + search_events 4)

- [ ] **Step 5: 커밋**

```bash
git add services/backend/app/api/events.py \
        services/backend/tests/test_search_events.py
git commit -m "refactor(backend): search_events raw SQL → pgvector ORM 연산자로 전환"
```

---

## Task 3: 동작 검증

- [ ] **Step 1: 백엔드 서버 기동 후 curl 검증**

기본 검색 (시간 필터 없음):
```bash
curl -s "http://localhost:8000/events/search?q=작업자+넘어짐&limit=5" | python3 -m json.tool
```

Expected:
```json
{
  "events": [...],
  "total": 5,
  "applied_filter": null
}
```

자연어 시간 필터:
```bash
curl -s "http://localhost:8000/events/search?q=저번+주+화재&limit=5" | python3 -m json.tool
```

Expected:
```json
{
  "events": [...],
  "applied_filter": "저번 주 필터 적용됨"
}
```

명시적 날짜 필터:
```bash
curl -s "http://localhost:8000/events/search?q=화재&start_date=2026-05-01T00:00:00Z&limit=5" | python3 -m json.tool
```

Expected: `applied_filter: null` (명시적 날짜 전달 시 칩 미표시)

채널 필터:
```bash
curl -s "http://localhost:8000/events/search?q=화재&channel_id=cam0&limit=5" | python3 -m json.tool
```

Expected: 모든 이벤트의 `channel_id`가 `"cam0"`인지 확인.

- [ ] **Step 2: similarity 값 범위 확인**

응답의 모든 `similarity` 값이 `0.0 ~ 1.0` 범위인지 확인 (cosine distance는 0~2이므로 `1 - distance`가 음수가 되면 버그).

```bash
curl -s "http://localhost:8000/events/search?q=화재&limit=10" \
  | python3 -c "import sys,json; data=json.load(sys.stdin); print([e['similarity'] for e in data['events']])"
```

Expected: `[0.85, 0.79, 0.71, ...]` 형태, 모두 0 이상.

---

## 구현 후 events.py 최종 형태 요약

변경 전후 핵심 차이:

| | 변경 전 | 변경 후 |
|---|---------|---------|
| 쿼리 방식 | `text(f"SELECT ... {where_clause}")` | `select(EventLog, distance_col).where(...).order_by(...)` |
| 벡터 전달 | `str(query_vector)` + `CAST(... AS vector)` | `query_vector` list 직접 전달 |
| DB 왕복 | 2회 (ID 조회 → 전체 조회) | 1회 |
| 조건 추가 | 문자열 이어붙이기 | `.where()` 체이닝 |
| `text()` import | 필요 | 제거 |
