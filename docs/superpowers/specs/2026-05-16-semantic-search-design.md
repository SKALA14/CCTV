# Semantic Search Enhancement — Design Spec

**Date:** 2026-05-16  
**Branch:** Search  
**Status:** Approved

---

## 배경 및 목표

현재 의미 기반 검색 파이프라인(쿼리 임베딩 → pgvector cosine 검색)은 동작하지만 두 가지 핵심 문제가 있다.

1. **시간 표현 처리 불가**: "저번 주 작업자 넘어진 상황"에서 "저번 주"는 벡터 유사도로 처리할 수 없어 날짜 필터가 적용되지 않음
2. **관련도 미표시**: `similarity` 값이 API에서 내려오지만 UI에 표시되지 않아 검색 품질을 판단할 수 없음

목표: 자연어 시간 표현 파싱 + 빠른 날짜 필터 UI + 관련도 표시로 검색 완성도를 높인다.

---

## 전체 구조

```
사용자 입력: "저번 주 작업자 넘어진 상황 있어?"
                    ↓
        [시간 표현 파서 — 백엔드]
                    ↓
    cleaned_query: "작업자 넘어진 상황"
    time_range:    (2026-05-09 ~ 2026-05-15)
    label:         "저번 주 필터 적용됨"
                    ↓
        [OpenAI Embedding(cleaned_query)]  +  [SQL date filter]
                    ↓
        pgvector cosine 검색 (WHERE occurred_at BETWEEN ...)
                    ↓
        결과 + similarity + applied_filter 반환
                    ↓
        [프론트엔드]
        - ResultCard: "87% 일치" 배지 표시
        - SearchBar 하단: "저번 주 필터 적용됨" 칩 표시
        - 빠른 필터 버튼: [오늘] [이번 주] [지난 7일] [이번 달]
```

---

## 백엔드

### 신규: `services/backend/app/api/time_parser.py`

정규식 기반 시간 표현 파싱 유틸리티.

**시그니처:**
```python
def parse_time_expression(query: str) -> tuple[str, datetime | None, datetime | None, str | None]:
    """
    Returns: (cleaned_query, start_dt, end_dt, label)
    시간 표현 없으면: (query, None, None, None)
    """
```

**커버 패턴:**

| 입력 표현 | start_dt | end_dt | label |
|-----------|----------|--------|-------|
| 오늘 | today 00:00 | now | "오늘 필터 적용됨" |
| 어제 | yesterday 00:00 | yesterday 23:59:59 | "어제 필터 적용됨" |
| 이번 주 | 이번 주 월요일 00:00 | now | "이번 주 필터 적용됨" |
| 저번 주 | 지난 주 월요일 00:00 | 지난 주 일요일 23:59:59 | "저번 주 필터 적용됨" |
| 지난 N일 / N일 전 | now - N days | now | "지난 N일 필터 적용됨" |
| 이번 달 | 이번 달 1일 00:00 | now | "이번 달 필터 적용됨" |
| 지난 달 | 지난 달 1일 00:00 | 지난 달 말일 23:59:59 | "지난 달 필터 적용됨" |

모든 datetime은 UTC 기준.

---

### 수정: `services/backend/app/api/events.py`

**`GET /events/search` 파라미터 추가:**

```
기존: q, channel_id, limit
추가: start_date (optional, ISO datetime), end_date (optional, ISO datetime)
```

**처리 순서:**
1. `parse_time_expression(q)` 호출 → `cleaned_query`, `start_dt`, `end_dt`, `label`
2. 프론트에서 `start_date`/`end_date`를 직접 전달한 경우 → 파서 결과 날짜를 무시하고 전달된 날짜 사용, `applied_filter`는 `null` 반환 (버튼이 활성화 상태이므로 칩 불필요)
3. 직접 전달이 없고 파서가 날짜를 추출한 경우 → 파서 날짜 사용, `applied_filter`에 `label` 반환
4. `cleaned_query`로 embedding 생성 (시간 표현 제거된 쿼리)
5. pgvector SQL에 `occurred_at BETWEEN :start AND :end` 조건 추가 (날짜 있을 때만)

---

### 수정: `services/backend/app/api/schemas.py`

```python
class EventListResponse(BaseModel):
    events: list[EventLogRead]
    total:  int
    skip:   int
    limit:  int
    applied_filter: str | None = None  # "저번 주 필터 적용됨"
```

---

## 프론트엔드

### 수정: `services/frontend/src/components/search/ResultCard.vue`

`event.similarity`가 있을 때만 관련도 배지 표시.

```
[채널명]  ·  05/09 14:32              [high]
작업자가 안전모를 착용하지 않고...    [87% 일치]
                                      [클립 재생]
```

- `v-if="event.similarity != null"`
- 표시값: `Math.round(event.similarity * 100) + '% 일치'`
- 일반 이벤트 목록(`/events`)에서는 similarity가 null이므로 미표시

---

### 수정: `services/frontend/src/views/SearchView.vue`

**빠른 필터 버튼** (SearchBar 아래):
```
[오늘]  [이번 주]  [지난 7일]  [이번 달]
```
- 선택 시 활성화 스타일, 재클릭 시 해제
- 선택된 버튼의 `start_date`/`end_date`를 API 호출 시 전달
- 버튼 선택 시 자연어 필터 칩이 있으면 제거 (버튼과 칩은 상호 배타적)

**자연어 필터 칩** (검색 실행 후 `applied_filter` 있을 때):
```
검색어에서 감지: [저번 주 필터 적용됨  ×]
```
- `×` 클릭 시 `q`만 유지하고 날짜 필터 없이 재검색
- 빠른 필터 버튼이 선택된 상태에서는 미표시 (버튼과 칩은 상호 배타적)

---

### 수정: `services/frontend/src/api/events.js`

```javascript
export const searchEvents = (query, channelId = null, startDate = null, endDate = null) =>
    api.get('/events/search', {
        params: { q: query, channel_id: channelId, start_date: startDate, end_date: endDate }
    }).then(r => r.data)
```

---

## 변경 범위 요약

| 파일 | 변경 유형 | 내용 |
|------|-----------|------|
| `backend/app/api/time_parser.py` | 신규 | 정규식 시간 표현 파싱 |
| `backend/app/api/events.py` | 수정 | 파서 호출, date filter, applied_filter 반환 |
| `backend/app/api/schemas.py` | 수정 | `applied_filter` 필드 추가 |
| `frontend/src/components/search/ResultCard.vue` | 수정 | similarity 배지 |
| `frontend/src/views/SearchView.vue` | 수정 | 빠른 필터 버튼, 필터 칩 |
| `frontend/src/api/events.js` | 수정 | start_date/end_date 파라미터 |

**변경하지 않는 것:** SearchBar, ResultList, ClipDetail, ChannelFilter, worker.py, DB 스키마, HNSW 인덱스

---

## 성공 기준

1. `"저번 주 작업자 넘어진 상황"` 검색 시 해당 기간 이벤트만 반환됨
2. 검색 결과 카드에 `"87% 일치"` 형태 배지가 표시됨
3. 빠른 필터 버튼 선택 시 해당 날짜 범위로 검색 결과가 필터링됨
4. `×` 클릭 시 날짜 필터 없이 동일 쿼리로 재검색됨
5. 일반 이벤트 목록(`/events`)에서는 similarity 배지 미표시
