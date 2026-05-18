# Semantic Search Enhancement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 자연어 시간 표현 파싱(규칙 기반) + 빠른 날짜 필터 UI + 검색 결과 관련도(similarity) 표시로 의미 기반 검색을 완성한다.

**Architecture:** 백엔드에 `time_parser.py`를 신규 추가해 쿼리에서 시간 표현을 추출·제거하고, `search_events` 엔드포인트에 날짜 필터(SQL WHERE)를 결합한다. 프론트엔드는 ResultCard에 similarity 배지를 추가하고, SearchView에 빠른 필터 버튼과 자연어 필터 칩을 추가한다.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy(async), pgvector, Vue 3 Composition API, Pinia

---

## 변경 파일 목록

| 파일 | 유형 | 역할 |
|------|------|------|
| `services/backend/app/api/time_parser.py` | 신규 | 정규식 기반 시간 표현 파싱 |
| `services/backend/tests/__init__.py` | 신규 | 테스트 패키지 |
| `services/backend/tests/test_time_parser.py` | 신규 | time_parser 단위 테스트 |
| `services/backend/app/api/schemas.py` | 수정 | `EventListResponse`에 `applied_filter` 추가 |
| `services/backend/app/api/events.py` | 수정 | 파서 호출 + 날짜 필터 + `applied_filter` 반환 |
| `services/frontend/src/api/events.js` | 수정 | `searchEvents`에 `startDate`/`endDate` 파라미터 추가 |
| `services/frontend/src/composables/useEvents.js` | 수정 | `appliedFilter` ref 노출, `search`에 날짜 파라미터 전달 |
| `services/frontend/src/components/search/ResultCard.vue` | 수정 | similarity 배지 추가 |
| `services/frontend/src/views/SearchView.vue` | 수정 | 빠른 필터 버튼 + 자연어 필터 칩 |

---

## Task 1: time_parser.py — 테스트 먼저 작성

**Files:**
- Create: `services/backend/tests/__init__.py`
- Create: `services/backend/tests/test_time_parser.py`

- [ ] **Step 1: 테스트 파일 작성**

`services/backend/tests/__init__.py` — 빈 파일 생성.

`services/backend/tests/test_time_parser.py`:

```python
from datetime import datetime, timezone
from unittest.mock import patch
import pytest

# 고정 기준 시각: 2026-05-16 (금요일) 12:00:00 UTC
FIXED_NOW = datetime(2026, 5, 16, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def mock_now():
    with patch("app.api.time_parser._now", return_value=FIXED_NOW):
        yield


def test_no_time_expression():
    from app.api.time_parser import parse_time_expression
    cleaned, start, end, label = parse_time_expression("작업자 넘어짐")
    assert cleaned == "작업자 넘어짐"
    assert start is None
    assert end is None
    assert label is None


def test_오늘():
    from app.api.time_parser import parse_time_expression
    cleaned, start, end, label = parse_time_expression("오늘 화재 발생")
    assert cleaned == "화재 발생"
    assert start == datetime(2026, 5, 16, 0, 0, 0, tzinfo=timezone.utc)
    assert end == FIXED_NOW
    assert label == "오늘 필터 적용됨"


def test_어제():
    from app.api.time_parser import parse_time_expression
    cleaned, start, end, label = parse_time_expression("어제 작업자 넘어짐")
    assert cleaned == "작업자 넘어짐"
    assert start == datetime(2026, 5, 15, 0, 0, 0, tzinfo=timezone.utc)
    assert end == datetime(2026, 5, 15, 23, 59, 59, 999999, tzinfo=timezone.utc)
    assert label == "어제 필터 적용됨"


def test_이번_주():
    from app.api.time_parser import parse_time_expression
    cleaned, start, end, label = parse_time_expression("이번 주 안전모 미착용")
    assert cleaned == "안전모 미착용"
    assert start == datetime(2026, 5, 11, 0, 0, 0, tzinfo=timezone.utc)  # 월요일
    assert end == FIXED_NOW
    assert label == "이번 주 필터 적용됨"


def test_저번_주():
    from app.api.time_parser import parse_time_expression
    cleaned, start, end, label = parse_time_expression("저번 주 작업자 넘어진 상황 있어")
    assert cleaned == "작업자 넘어진 상황 있어"
    assert start == datetime(2026, 5, 4, 0, 0, 0, tzinfo=timezone.utc)    # 저번 주 월요일
    assert end == datetime(2026, 5, 10, 23, 59, 59, 999999, tzinfo=timezone.utc)  # 저번 주 일요일
    assert label == "저번 주 필터 적용됨"


def test_지난_주_alias():
    from app.api.time_parser import parse_time_expression
    cleaned, start, end, label = parse_time_expression("지난 주 화재")
    assert start == datetime(2026, 5, 4, 0, 0, 0, tzinfo=timezone.utc)
    assert label == "저번 주 필터 적용됨"


def test_지난_N일():
    from app.api.time_parser import parse_time_expression
    cleaned, start, end, label = parse_time_expression("지난 3일 화재")
    assert cleaned == "화재"
    assert start == datetime(2026, 5, 13, 0, 0, 0, tzinfo=timezone.utc)
    assert end == FIXED_NOW
    assert label == "지난 3일 필터 적용됨"


def test_N일_전():
    from app.api.time_parser import parse_time_expression
    cleaned, start, end, label = parse_time_expression("5일 전 침입 감지")
    assert cleaned == "침입 감지"
    assert start == datetime(2026, 5, 11, 0, 0, 0, tzinfo=timezone.utc)
    assert label == "지난 5일 필터 적용됨"


def test_이번_달():
    from app.api.time_parser import parse_time_expression
    cleaned, start, end, label = parse_time_expression("이번 달 이벤트")
    assert cleaned == "이벤트"
    assert start == datetime(2026, 5, 1, 0, 0, 0, tzinfo=timezone.utc)
    assert end == FIXED_NOW
    assert label == "이번 달 필터 적용됨"


def test_지난_달():
    from app.api.time_parser import parse_time_expression
    cleaned, start, end, label = parse_time_expression("지난 달 화재")
    assert cleaned == "화재"
    assert start == datetime(2026, 4, 1, 0, 0, 0, tzinfo=timezone.utc)
    assert end == datetime(2026, 4, 30, 23, 59, 59, 999999, tzinfo=timezone.utc)
    assert label == "지난 달 필터 적용됨"


def test_query_only_time_expression():
    from app.api.time_parser import parse_time_expression
    cleaned, start, end, label = parse_time_expression("어제")
    assert cleaned == ""
    assert label == "어제 필터 적용됨"
```

- [ ] **Step 2: 테스트 실행 — 실패 확인**

```bash
cd services/backend && python -m pytest tests/test_time_parser.py -v
```

Expected: `ModuleNotFoundError: No module named 'app.api.time_parser'`

---

## Task 2: time_parser.py — 구현

**Files:**
- Create: `services/backend/app/api/time_parser.py`

- [ ] **Step 1: time_parser.py 작성**

```python
import re
from datetime import datetime, timedelta, timezone


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


def _start_of_day(dt: datetime) -> datetime:
    return dt.replace(hour=0, minute=0, second=0, microsecond=0)


def _end_of_day(dt: datetime) -> datetime:
    return dt.replace(hour=23, minute=59, second=59, microsecond=999999)


def _start_of_week(dt: datetime) -> datetime:
    monday = dt - timedelta(days=dt.weekday())
    return _start_of_day(monday)


_PATTERNS = [
    (re.compile(r'지난\s*(\d+)\s*일'), 'LAST_N_DAYS_A'),
    (re.compile(r'(\d+)\s*일\s*전'),   'LAST_N_DAYS_B'),
    (re.compile(r'오늘'),              'TODAY'),
    (re.compile(r'어제'),              'YESTERDAY'),
    (re.compile(r'저번\s*주|지난\s*주'), 'LAST_WEEK'),
    (re.compile(r'이번\s*주'),         'THIS_WEEK'),
    (re.compile(r'지난\s*달'),         'LAST_MONTH'),
    (re.compile(r'이번\s*달'),         'THIS_MONTH'),
]


def parse_time_expression(
    query: str,
) -> tuple[str, datetime | None, datetime | None, str | None]:
    now = _now()

    for pattern, key in _PATTERNS:
        m = pattern.search(query)
        if not m:
            continue

        cleaned = pattern.sub('', query).strip()
        cleaned = re.sub(r'^[\s,?!]+|[\s,?!]+$', '', cleaned)

        if key == 'LAST_N_DAYS_A':
            n = int(m.group(1))
            start = _start_of_day(now - timedelta(days=n))
            return cleaned, start, now, f"지난 {n}일 필터 적용됨"

        if key == 'LAST_N_DAYS_B':
            n = int(m.group(1))
            start = _start_of_day(now - timedelta(days=n))
            return cleaned, start, now, f"지난 {n}일 필터 적용됨"

        if key == 'TODAY':
            return cleaned, _start_of_day(now), now, "오늘 필터 적용됨"

        if key == 'YESTERDAY':
            yesterday = now - timedelta(days=1)
            return cleaned, _start_of_day(yesterday), _end_of_day(yesterday), "어제 필터 적용됨"

        if key == 'THIS_WEEK':
            return cleaned, _start_of_week(now), now, "이번 주 필터 적용됨"

        if key == 'LAST_WEEK':
            last_monday = _start_of_week(now) - timedelta(weeks=1)
            last_sunday = _end_of_day(last_monday + timedelta(days=6))
            return cleaned, last_monday, last_sunday, "저번 주 필터 적용됨"

        if key == 'THIS_MONTH':
            start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            return cleaned, start, now, "이번 달 필터 적용됨"

        if key == 'LAST_MONTH':
            first_of_this = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            last_month_end = first_of_this - timedelta(seconds=1)
            last_month_start = last_month_end.replace(
                day=1, hour=0, minute=0, second=0, microsecond=0
            )
            return cleaned, last_month_start, _end_of_day(last_month_end), "지난 달 필터 적용됨"

    return query, None, None, None
```

- [ ] **Step 2: 테스트 실행 — 통과 확인**

```bash
cd services/backend && python -m pytest tests/test_time_parser.py -v
```

Expected:
```
test_no_time_expression PASSED
test_오늘 PASSED
test_어제 PASSED
test_이번_주 PASSED
test_저번_주 PASSED
test_지난_주_alias PASSED
test_지난_N일 PASSED
test_N일_전 PASSED
test_이번_달 PASSED
test_지난_달 PASSED
test_query_only_time_expression PASSED
11 passed in 0.XXs
```

- [ ] **Step 3: 커밋**

```bash
git add services/backend/app/api/time_parser.py \
        services/backend/tests/__init__.py \
        services/backend/tests/test_time_parser.py
git commit -m "feat(backend): 자연어 시간 표현 파싱 유틸리티 추가 (time_parser)"
```

---

## Task 3: schemas.py — applied_filter 필드 추가

**Files:**
- Modify: `services/backend/app/api/schemas.py`

- [ ] **Step 1: EventListResponse에 applied_filter 추가**

`services/backend/app/api/schemas.py` 전체를 아래로 교체:

```python
import uuid
from datetime import datetime

from pydantic import BaseModel


class EventLogRead(BaseModel):
    id:            uuid.UUID
    channel_id:    str
    channel_name:  str | None
    pipeline:      str
    event_type:    str
    danger_level:  str
    reason:        str | None
    confidence:    float | None
    vlm_confidence: float | None
    pose_event:    str | None
    source_model:  str | None
    frame_path:    str | None
    thumbnail_url: str | None
    clip_url:      str | None
    source_path:   str | None
    occurred_at:   datetime
    created_at:    datetime
    similarity:    float | None = None


class EventListResponse(BaseModel):
    events:         list[EventLogRead]
    total:          int
    skip:           int
    limit:          int
    applied_filter: str | None = None
```

- [ ] **Step 2: 커밋**

```bash
git add services/backend/app/api/schemas.py
git commit -m "feat(backend): EventListResponse에 applied_filter 필드 추가"
```

---

## Task 4: events.py — 파서 통합 + 날짜 필터

**Files:**
- Modify: `services/backend/app/api/events.py`

- [ ] **Step 1: events.py 수정**

`services/backend/app/api/events.py`의 import 블록을 아래로 교체:

```python
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from openai import AsyncOpenAI
from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.db.models import EventLog, CctvChannel
from app.api.schemas import EventLogRead, EventListResponse
from app.api.time_parser import parse_time_expression
```

- [ ] **Step 2: search_events 함수 전체 교체**

`services/backend/app/api/events.py`의 `search_events` 함수(line 81~131)를 아래로 교체:

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

    # 프론트에서 명시적으로 전달한 날짜가 있으면 파서 결과보다 우선
    if start_date or end_date:
        active_start, active_end, applied_filter = start_date, end_date, None
    else:
        active_start, active_end, applied_filter = parsed_start, parsed_end, label

    response = await _openai.embeddings.create(
        model="text-embedding-3-small",
        input=cleaned_query or q,
    )
    query_vector = response.data[0].embedding

    where_clause = "WHERE embedding IS NOT NULL"
    params: dict = {"vec": str(query_vector), "limit": limit}

    if channel_id:
        where_clause += " AND camera_id = :channel_id"
        params["channel_id"] = channel_id
    if active_start:
        where_clause += " AND occurred_at >= :start_date"
        params["start_date"] = active_start
    if active_end:
        where_clause += " AND occurred_at <= :end_date"
        params["end_date"] = active_end

    rows = await db.execute(
        text(f"""
            SELECT event_id,
                   (embedding <=> CAST(:vec AS vector)) AS distance
            FROM event_logs
            {where_clause}
            ORDER BY distance
            LIMIT :limit
        """),
        params,
    )
    id_dist = {str(r.event_id): r.distance for r in rows}

    if not id_dist:
        return EventListResponse(
            events=[], total=0, skip=0, limit=limit, applied_filter=applied_filter
        )

    result = await db.execute(
        select(EventLog).where(EventLog.event_id.in_([uuid.UUID(k) for k in id_dist]))
    )
    events_map = {str(e.event_id): e for e in result.scalars().all()}
    ordered = [events_map[k] for k in id_dist if k in events_map]

    channel_names = await _fetch_channel_names(db, [e.camera_id for e in ordered])
    return EventListResponse(
        events=[
            _to_schema(e, channel_names.get(e.camera_id), similarity=round(1 - id_dist[str(e.event_id)], 4))
            for e in ordered
        ],
        total=len(ordered),
        skip=0,
        limit=limit,
        applied_filter=applied_filter,
    )
```

- [ ] **Step 3: 동작 확인 (백엔드 실행 중인 경우)**

```bash
curl "http://localhost:8000/events/search?q=저번+주+작업자+넘어짐" | python3 -m json.tool
```

Expected: `applied_filter: "저번 주 필터 적용됨"`, 날짜 범위 안의 이벤트만 반환.

```bash
curl "http://localhost:8000/events/search?q=화재&start_date=2026-05-01T00:00:00Z" | python3 -m json.tool
```

Expected: `applied_filter: null` (명시적 날짜 전달 시 칩 미표시).

- [ ] **Step 4: 커밋**

```bash
git add services/backend/app/api/events.py
git commit -m "feat(backend): search 엔드포인트에 시간 파서 + 날짜 필터 통합"
```

---

## Task 5: events.js — API 클라이언트 날짜 파라미터 추가

**Files:**
- Modify: `services/frontend/src/api/events.js`

- [ ] **Step 1: searchEvents 함수 수정**

`services/frontend/src/api/events.js` 전체를 아래로 교체:

```javascript
import api from './index.js'

export const fetchEvents = (params = {}) =>
    api.get('/events', { params }).then(r => r.data)

export const fetchEventById = (id) =>
    api.get(`/events/${id}`).then(r => r.data)

export const searchEvents = (query, channelId = null, startDate = null, endDate = null) =>
    api.get('/events/search', {
        params: {
            q: query,
            channel_id: channelId,
            start_date: startDate,
            end_date:   endDate,
        },
    }).then(r => r.data)
```

- [ ] **Step 2: 커밋**

```bash
git add services/frontend/src/api/events.js
git commit -m "feat(frontend): searchEvents API에 날짜 파라미터 추가"
```

---

## Task 6: useEvents.js — appliedFilter 노출 + 날짜 파라미터 전달

**Files:**
- Modify: `services/frontend/src/composables/useEvents.js`

- [ ] **Step 1: useEvents.js 수정**

`services/frontend/src/composables/useEvents.js` 전체를 아래로 교체:

```javascript
import { ref } from 'vue'
import { DUMMY_MODE } from '../constants/mode.js'
import { DUMMY_EVENTS } from '../constants/dummyData.js'
import { fetchEvents, searchEvents } from '../api/events.js'

export function useEvents() {
  const events        = ref([])
  const loading       = ref(false)
  const error         = ref(null)
  const appliedFilter = ref(null)

  async function load(params = {}) {
    if (DUMMY_MODE) {
      events.value = DUMMY_EVENTS
      return
    }
    loading.value = true
    error.value   = null
    try {
      const res     = await fetchEvents(params)
      events.value  = Array.isArray(res) ? res : (res.events ?? [])
    } catch (e) {
      error.value = e.response?.data?.detail ?? e.message
    } finally {
      loading.value = false
    }
  }

  async function search(query, channelId = null, startDate = null, endDate = null) {
    if (DUMMY_MODE) {
      const q = (query || '').trim().toLowerCase()
      events.value = DUMMY_EVENTS.filter(ev => {
        const matchChannel = !channelId || ev.camera_id === channelId
        const matchText    = !q || [ev.description, ev.event_type, ev.channel_name]
          .some(s => s && s.toLowerCase().includes(q))
        return matchChannel && matchText
      })
      return
    }
    loading.value       = true
    error.value         = null
    appliedFilter.value = null
    try {
      const res           = await searchEvents(query, channelId, startDate, endDate)
      events.value        = Array.isArray(res) ? res : (res.events ?? [])
      appliedFilter.value = res.applied_filter ?? null
    } catch (e) {
      error.value = e.response?.data?.detail ?? e.message
    } finally {
      loading.value = false
    }
  }

  return { events, loading, error, appliedFilter, load, search }
}
```

- [ ] **Step 2: 커밋**

```bash
git add services/frontend/src/composables/useEvents.js
git commit -m "feat(frontend): useEvents에 appliedFilter 노출 및 날짜 파라미터 전달"
```

---

## Task 7: ResultCard.vue — similarity 배지 추가

**Files:**
- Modify: `services/frontend/src/components/search/ResultCard.vue`

- [ ] **Step 1: 배지 영역 수정**

`services/frontend/src/components/search/ResultCard.vue`의 배지 + 버튼 div(line 28~38)를 아래로 교체:

```html
    <!-- 배지 + 버튼 -->
    <div class="flex flex-col items-end justify-between flex-shrink-0 gap-2">
      <div class="flex items-center gap-1.5">
        <span
          v-if="event.similarity != null"
          class="text-xs tabular-nums"
          style="color: var(--text-muted);"
        >{{ Math.round(event.similarity * 100) }}% 일치</span>
        <span class="danger-badge" :class="event.danger_level">{{ event.danger_level }}</span>
      </div>
      <button
        class="px-3 py-1.5 rounded-lg text-xs transition-colors whitespace-nowrap"
        style="border: 1px solid var(--border); color: var(--text-muted);"
        @mouseover="e => { e.currentTarget.style.borderColor = 'var(--text-muted)'; e.currentTarget.style.color = 'var(--text-primary)'; }"
        @mouseleave="e => { e.currentTarget.style.borderColor = 'var(--border)'; e.currentTarget.style.color = 'var(--text-muted)'; }"
        @click="goToClip"
      >클립 재생</button>
    </div>
```

- [ ] **Step 2: 동작 확인**

검색 후 ResultCard에 `"87% 일치"` 형태 텍스트가 danger-badge 왼쪽에 표시되는지 확인.  
`/events` 일반 목록에서는 배지가 미표시되는지 확인 (similarity가 null이므로).

- [ ] **Step 3: 커밋**

```bash
git add services/frontend/src/components/search/ResultCard.vue
git commit -m "feat(frontend): ResultCard에 similarity 관련도 배지 추가"
```

---

## Task 8: SearchView.vue — 빠른 필터 버튼 + 자연어 필터 칩

**Files:**
- Modify: `services/frontend/src/views/SearchView.vue`

- [ ] **Step 1: SearchView.vue 전체 교체**

```vue
<template>
  <div class="p-4 max-w-3xl mx-auto">
    <div class="mb-4 space-y-3">
      <SearchBar @search="handleSearch" />

      <!-- 빠른 날짜 필터 버튼 -->
      <div class="flex flex-wrap gap-2">
        <span
          v-for="f in QUICK_FILTERS"
          :key="f.key"
          class="px-3 py-1 rounded-full text-sm cursor-pointer transition-colors select-none"
          :class="selectedQuickFilter === f.key ? 'bg-blue-600 text-white' : ''"
          :style="selectedQuickFilter !== f.key
            ? 'border: 1px solid var(--border); color: var(--text-muted);'
            : 'border: 1px solid transparent;'"
          @click="handleQuickFilter(f.key)"
        >{{ f.label }}</span>
      </div>

      <!-- 자연어 필터 칩 -->
      <div
        v-if="appliedFilter && !selectedQuickFilter"
        class="flex items-center gap-2"
      >
        <span class="text-xs" style="color: var(--text-muted);">검색어에서 감지:</span>
        <span
          class="flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs"
          style="background: var(--bg-elevated); border: 1px solid var(--border); color: var(--text-primary);"
        >
          {{ appliedFilter }}
          <button
            class="ml-0.5 leading-none"
            style="color: var(--text-muted);"
            @click="clearAppliedFilter"
          >×</button>
        </span>
      </div>

      <ChannelFilter
        :channels="channels"
        v-model="selectedChannelId"
      />
    </div>

    <ResultList
      :events="events"
      :loading="loading"
      :error="error"
    />
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import SearchBar    from '../components/search/SearchBar.vue'
import ChannelFilter from '../components/search/ChannelFilter.vue'
import ResultList   from '../components/search/ResultList.vue'
import { useEvents }   from '../composables/useEvents.js'
import { useChannels } from '../composables/useChannels.js'
import { useEventStore } from '../stores/eventStore.js'

const { events, loading, error, appliedFilter, load, search } = useEvents()
const { slots }  = useChannels()
const channels   = computed(() => slots.value.filter(Boolean))
const eventStore = useEventStore()

const selectedChannelId  = ref(null)
const lastQuery          = ref('')
const selectedQuickFilter = ref(null)

const QUICK_FILTERS = [
  { key: 'today',      label: '오늘' },
  { key: 'this_week',  label: '이번 주' },
  { key: 'last_7',     label: '지난 7일' },
  { key: 'this_month', label: '이번 달' },
]

function getQuickFilterDates(key) {
  const now      = new Date()
  const dayStart = (d) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).toISOString()

  if (key === 'today') {
    return { startDate: dayStart(now), endDate: now.toISOString() }
  }
  if (key === 'this_week') {
    const monday = new Date(now)
    const day = now.getDay()
    monday.setDate(now.getDate() - (day === 0 ? 6 : day - 1))
    return { startDate: dayStart(monday), endDate: now.toISOString() }
  }
  if (key === 'last_7') {
    const start = new Date(now)
    start.setDate(start.getDate() - 7)
    return { startDate: dayStart(start), endDate: now.toISOString() }
  }
  if (key === 'this_month') {
    return {
      startDate: new Date(now.getFullYear(), now.getMonth(), 1).toISOString(),
      endDate:   now.toISOString(),
    }
  }
  return { startDate: null, endDate: null }
}

async function handleSearch(query, startDate = null, endDate = null) {
  lastQuery.value = query
  await search(query, selectedChannelId.value, startDate, endDate)
  eventStore.setSearchResults(events.value)
}

async function handleQuickFilter(key) {
  if (selectedQuickFilter.value === key) {
    selectedQuickFilter.value = null
    if (lastQuery.value) await handleSearch(lastQuery.value)
    return
  }
  selectedQuickFilter.value = key
  if (lastQuery.value) {
    const { startDate, endDate } = getQuickFilterDates(key)
    await handleSearch(lastQuery.value, startDate, endDate)
  }
}

async function clearAppliedFilter() {
  await handleSearch(lastQuery.value)
}

watch(selectedChannelId, async () => {
  if (lastQuery.value) {
    const dates = selectedQuickFilter.value
      ? getQuickFilterDates(selectedQuickFilter.value)
      : { startDate: null, endDate: null }
    await handleSearch(lastQuery.value, dates.startDate, dates.endDate)
  } else {
    const params = selectedChannelId.value ? { channel_id: selectedChannelId.value } : {}
    await load(params)
    eventStore.setSearchResults(events.value)
  }
})
</script>
```

- [ ] **Step 2: 동작 확인 체크리스트**

```
□ "저번 주 작업자 넘어짐" 검색 → "저번 주 필터 적용됨" 칩 표시, 해당 기간 이벤트만 반환
□ 칩의 × 클릭 → 날짜 필터 없이 동일 쿼리 재검색, 칩 사라짐
□ [이번 주] 버튼 클릭 → 버튼 파란색, 해당 기간 이벤트 필터링
□ [이번 주] 버튼 재클릭 → 버튼 해제, 필터 없이 재검색
□ 빠른 필터 활성 상태에서 자연어 시간 표현 검색 → 칩 미표시 (버튼이 표시 중)
□ 채널 필터 변경 → 현재 활성된 날짜 필터 유지한 채 재검색
```

- [ ] **Step 3: 커밋**

```bash
git add services/frontend/src/views/SearchView.vue
git commit -m "feat(frontend): 빠른 날짜 필터 버튼 및 자연어 필터 칩 추가"
```

---

## 최종 검증

- [ ] **전체 시나리오 테스트**

```
1. "저번 주 작업자 넘어진 상황 있어?" 검색
   → applied_filter: "저번 주 필터 적용됨" 칩 표시
   → 저번 주 날짜 범위 이벤트만 반환
   → 각 ResultCard에 "N% 일치" 배지 표시

2. [지난 7일] 버튼 클릭
   → 버튼 파란색 활성화
   → 칩 미표시

3. "작업자 넘어짐" 검색 (시간 표현 없음)
   → applied_filter: null, 칩 없음
   → 전체 기간 의미 검색 결과 반환
   → similarity 배지 표시

4. 일반 대시보드(/events 목록)
   → ResultCard에 similarity 배지 없음
```

- [ ] **백엔드 테스트 최종 실행**

```bash
cd services/backend && python -m pytest tests/test_time_parser.py -v
```

Expected: `11 passed`
