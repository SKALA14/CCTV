# 체크리스트 직접 편집(Human-in-the-loop) + 메뉴얼 증분 업데이트 설계

**작성일:** 2026-06-10
**브랜치:** `dev2` (dev1 `a423337`에서 분기)

## 목표

체크리스트 에이전트에 두 가지 운영 기능을 추가한다.

1. **직접 편집(F1):** 확정 저장된 공통/구역별 체크리스트를 메뉴얼 페이지에서 언제든 다시 열어 항목을 add/edit/delete 한다. (자연어 refine 외에 사람이 직접 손대는 경로)
2. **증분 업데이트(F2):** 이미 체크리스트가 있는 현장에 메뉴얼이 A→A'로 갱신됐을 때, 처음부터 다시 생성하지 않고 에이전트가 기존 체크리스트와 새 PDF를 비교해 **추가 항목 / 삭제 후보**만 추려 사용자 수락 후 기존에 병합한다.

## 핵심 결정 사항 (확정)

| 항목 | 결정 |
|---|---|
| F1 편집 시점 | 확정 후 언제든 (저장본 재오픈 편집) |
| F1 편집 범위 | 공통(static/dynamic) + 구역별 모두 |
| F2 진입 | 사용자가 선택 (증분 병합 vs 전체 재생성) |
| F2 diff 범위 | 추가 + 삭제 후보 (수정 매칭 없음) |
| 공통↔구역 관계 | 공통 변경 시 에이전트가 새 항목을 관련 구역에 자동 배치, 삭제는 전 구역 제거 → 이후 수동 보정 |
| 데이터 모델 | 구조화 `checklist.json` 단일 원본, `.md`+Redis는 파생 재생성 (접근법 A) |

## 현재 상태(변경 전)

`POST /manuals/confirm`이 저장하는 것:
- `{PROMPTS_DIR}/{site}/static_checklist.md`, `dynamic_checklist.md` — 번호 텍스트, 인퍼런스(`vlm/client`)가 읽음
- `{PROMPTS_DIR}/{site}/zone_{safe}_static.md`, `zone_{safe}_dynamic.md`
- Redis `checklist:{sid}:static:categories` 등 — "항목 1-based index → 카테고리 코드" HSET 맵

문제: **구조화된 source of truth가 없다.** 카테고리 `label`과 구역 구조가 별도로 보존되지 않아, 확정본을 편집하거나 diff하려면 `.md`를 역파싱해야 하고 카테고리 정보가 소실된다.

`analyze`/`refine`/`subset_by_zones`/`normalize_categories`는 `checklist_agent.py`에 존재하며 LLM(OpenAI) 1회 호출 + Redis 세션(TTL 3600s) 기반.

---

## 아키텍처

### 섹션 1 — 데이터 모델 & 파생 생성

**단일 원본:** `{PROMPTS_DIR}/{site}/checklist.json`

```jsonc
{
  "static":  { "categories": [ { "code": "FIRE", "label": "소방", "items": ["..."] } ] },
  "dynamic": { "categories": [ { "code": "FALL", "label": "낙상", "items": ["..."] } ] },
  "zones":   [ { "zone": "정문", "static": ["..."], "dynamic": ["..."] } ]
}
```

- 평탄화된 `static`/`dynamic` 항목 리스트는 categories의 items를 순서대로 이은 것(별도 저장 안 함, 파생).
- **파생물 재생성:** 저장(`confirm`/F1 edit/F2 merge) 시 항상 JSON으로부터 `.md` 파일들 + Redis 카테고리 맵을 재생성한다. 인퍼런스가 읽는 파일/키 포맷은 **변경 없음**.
- 공통 헬퍼 `_persist_checklist(sid, structured)`로 추출 — confirm/edit/merge 세 경로가 공유(현재 `confirm_manual` 본문 로직 재사용).
- **기존 현장 호환:** `checklist.json`이 없으면 첫 `GET`에서 기존 `.md` + Redis 맵 + per-zone `.md`를 1회 역구성해 JSON을 만든다. 카테고리 label이 복원 불가하면 `label = code`로 fallback.

### 섹션 2 — F1 편집 (백엔드)

`services/backend/app/api/manuals.py`

- `GET /manuals/checklist/full?site_id=` → 섹션 1 구조 JSON 반환. JSON 없으면 역구성.
- `PUT /manuals/checklist?site_id=` → 편집된 구조 JSON을 받아 `_persist_checklist`로 저장.
- 새 항목 카테고리: 편집 UI가 기존 카테고리 중 선택해 전달(기본 `GENERAL`/`일반`). 백엔드는 별도 LLM 호출 없음.
- 권한: 기존 `require_admin` + `_effective_site_id(current_user, site_id)` 그대로. superadmin은 site_id 지정 시에만 쓰기.
- 입력 검증: 빈 항목 문자열 제거, 카테고리 code 누락 시 `GENERAL`.

### 섹션 3 — F1 편집 (프론트)

`services/frontend/src/views/ManualView.vue` (+ 필요 시 컴포넌트 분리 `ChecklistEditorInline.vue`)

- "확정 체크리스트" read-only `<pre>` 영역을 **편집 가능 리스트**로 교체.
- 공통(static/dynamic) + 구역별을 탭/섹션으로 구분, 항목 행마다 inline edit, 삭제 버튼, "+ 항목 추가"(카테고리 드롭다운).
- "저장"(PUT) / "취소"(원복). 저장 성공 토스트.
- 권한: `canManage`(admin 또는 superadmin+선택현장)일 때만 편집 컨트롤 노출. viewer는 read-only 유지.

### 섹션 4 — F2 증분 diff (에이전트)

`services/backend/app/api/agent/checklist_agent.py`

- `diff_checklist(existing_items: list[str], new_pdf_text: str) -> dict` 추가.
  - 새 PDF 텍스트에서 항목을 추출하고, 기존 항목과 **의미 기반 매칭**(LLM 1회 호출)해
    `{ "added": [...], "removed_candidates": [...] }` 반환.
  - `added` = 새 PDF에 있고 기존에 의미상 없는 항목.
  - `removed_candidates` = 기존에 있고 새 PDF에 의미상 사라진 항목.
  - 수정(문구 변경) 매칭은 하지 않음(결정대로). 문구만 바뀐 항목은 매칭되면 변화 없음 처리, 안 되면 added+removed로 자연 노출.
- static/dynamic 각각 호출.

### 섹션 5 — F2 병합 (백엔드 + 자동 구역배치)

- `POST /manuals/analyze-diff?site_id=` (multipart PDF): 기존 `checklist.json` 로드 → static/dynamic `diff_checklist` → `{ static: {added, removed_candidates}, dynamic: {...} }` 반환. 세션 불필요(stateless).
- `POST /manuals/merge?site_id=`: 사용자가 수락한 `{ static_add, static_remove, dynamic_add, dynamic_remove }`를 받아:
  - 추가 항목: 카테고리 미상이므로 `GENERAL`(일반)로 분류해 기존 JSON에 append(사용자는 이후 F1 편집기로 재분류 가능). **새 항목에만** `subset_by_zones`를 돌려 관련 구역에 자동 배치.
  - 삭제 항목: 공통 categories + 모든 zones에서 제거.
  - `_persist_checklist`로 저장.

### 섹션 6 — F2 프론트

`ManualView.vue` + `api/manuals.js`

- PDF 업로드 시 해당 현장에 `checklist.json`(또는 기존 `.md`)이 있으면 **모드 선택 UI**: "전체 재생성" / "증분 병합".
  - 전체 재생성 → 기존 `analyze` 플로우.
  - 증분 병합 → `analyze-diff` 호출 → **diff 리뷰 화면**: 추가 항목(기본 체크)/삭제 후보(기본 해제) 각각 체크박스 → "병합"(merge) 호출.
- 병합 후 확정 체크리스트 영역 갱신.

### 섹션 7 — 테스트

- 백엔드 단위테스트(`services/backend/tests/`):
  - `_persist_checklist`: JSON → `.md`/Redis 파생물 정확성, 라운드트립(저장→GET 동일).
  - 기존 현장 역구성(JSON 없을 때 `.md`+Redis에서 복원).
  - `diff_checklist`: OpenAI 호출 모킹, added/removed_candidates 분류.
  - merge: 추가 시 새 항목만 구역 배치, 삭제 시 전 구역 제거.
- 에이전트 LLM 호출은 전부 모킹(실제 API 호출 없음).
- 인퍼런스가 읽는 파일/Redis 포맷 불변 회귀 확인.

## 비목표 (YAGNI)

- 체크리스트 버전 히스토리/롤백.
- 수정(문구 변경) 의미 매칭.
- 체크리스트 DB 이전(Postgres) — 파일 기반 유지.
- 실시간 협업 편집.

## 영향받지 않는 것 (회귀 금지)

- 인퍼런스 `vlm/client` 체크리스트 로딩(파일/Redis 포맷 그대로).
- detection→event→notification 파이프라인.
- 로그인/권한/멀티테넌시 격리(`_effective_site_id` 재사용).
- 기존 `analyze`/`refine`/`confirm` 플로우(전체 재생성 경로로 유지).
