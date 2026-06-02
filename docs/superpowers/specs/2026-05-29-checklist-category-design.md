# 체크리스트 카테고리 고도화 설계

**날짜**: 2026-05-29  
**브랜치**: dev1-woos  
**작성자**: brainstorming 세션

---

## 배경 및 문제 정의

### 현재 문제

PDF에서 체크리스트를 생성해 VLM 프롬프트에 주입하는 구조는 갖춰져 있으나, VLM의 출력 `anomaly_type`이 하드코딩된 고정 목록에 의존한다.

```
"stacking" | "blocked_path" | "damaged_facility" | "equipment_issue"  (static)
"intrusion" | "fight" | "fall" | "evacuation"                         (dynamic)
```

체크리스트 항목이 9개여도 VLM은 이 4가지 중 하나만 출력하므로, 체크리스트가 탐지 결과에 실질적으로 반영되지 않는다.

### 핵심 원인

- 체크리스트 항목과 `anomaly_type` 사이에 연결이 없음
- VLM이 체크리스트를 참고 맥락으로만 사용하고, 출력은 별도 하드코딩 목록에서 선택

---

## 설계 목표

1. `anomaly_type`을 체크리스트 기반으로 동적 생성
2. 의미 중복 카테고리 방지 (카테고리 폭발 억제)
3. DB 스키마·프론트엔드·inference 코드 변경 최소화
4. 하위 호환 유지 (categories 미전달 시 기존 동작)

---

## 핵심 아이디어: 정규화 단계 추가

체크리스트 항목 생성 후, 별도 LLM 호출로 의미가 겹치는 항목들을 하나의 카테고리 코드로 묶는다.

```
[생성된 항목들]
- 안전복장 미착용인가?
- 구명복을 착용하지 않았는가?
- 크레인 작업반경 내 무단출입인가?
        ↓ normalize_categories() LLM 호출
[정규화 결과]
PPE_MISSING:      ["안전복장 미착용인가?", "구명복 미착용인가?"]
ACCESS_VIOLATION: ["크레인 작업반경 내 무단출입인가?"]
```

카테고리 수는 문서마다 다르게 생성되지만, 의미 중복은 제거된다. 하드코딩 없음.

---

## 전체 데이터 흐름

```
[1] PDF 업로드
    POST /manuals/analyze
         │
         ├─ extract_text_from_pdf()          # 기존 그대로
         ├─ analyze_pdf()                    # 기존 그대로
         └─ normalize_categories() [신규]    # static/dynamic 각각 LLM 1회 호출
              │
              └─ 응답: static, dynamic, static_categories, dynamic_categories, zones

[2] 프론트 검토 후 확정
    POST /manuals/confirm
         │
         ├─ static_checklist.md 저장
         │   "[PPE_MISSING] 안전복장 미착용인가?"  ← 코드 태그 포함
         ├─ dynamic_checklist.md 저장
         └─ zone_{name}_{static|dynamic}.md 저장

[3] VLM 탐지
    inference render_prompt()
         │
         ├─ _load_checklist() → .md 파일 읽음  # 기존 그대로
         └─ .j2 템플릿에 주입 (안내 문구만 수정)

[4] VLM 응답
    anomaly_type: "PPE_MISSING"   ← 동적 코드 (프롬프트에서 읽은 태그)
    anomaly_type: "normal"        ← 이상 없음

[5] DB 저장 / Slack 알림
    worker.py → event_logs.anomaly_type = "PPE_MISSING"  # String(50) 그대로
    slack.py  → ANOMALY_TYPE_KO 미매핑 시 raw 코드 그대로 출력 (의도적)
```

---

## 컴포넌트별 설계

### 1. `normalize_categories()` (신규, `checklist_agent.py`)

**시그니처**
```python
async def normalize_categories(checklist: dict) -> dict:
    """
    입력:  analyze_pdf() 결과 {static: [...], dynamic: [...]}
    출력:  {
        "static": {
            "items": [...],
            "categories": [
                {"code": "PPE_MISSING", "label": "보호장비 미착용", "items": [...]}
            ]
        },
        "dynamic": { ... }
    }
    """
```

**LLM 프롬프트 설계**
```
다음은 CCTV 안전 체크리스트 항목들이다.
의미가 겹치거나 같은 위험 유형에 속하는 항목들을 묶어 카테고리를 만들어라.

[규칙]
- 카테고리 코드: 영문+언더스코어, 20자 이내, 명사형 (예: PPE_MISSING, ACCESS_VIOLATION)
- 의미가 명확히 다른 항목은 별도 카테고리로 분리
- 항목 1개만 있어도 카테고리로 만들 것
- 항목 원문은 수정하지 말 것

{"categories": [{"code": "...", "label": "...(한국어)", "items": ["원문 질문?"]}]}
```

**에러 처리**

| 상황 | 처리 |
|------|------|
| LLM이 빈 배열 반환 | 전체 items를 `GENERAL` 단일 카테고리로 fallback |
| JSON 파싱 실패 | categories 없이 items만 반환 (서비스 중단 없음) |
| 일부 items 누락 | 누락 항목을 `UNCATEGORIZED`로 자동 보완 |

---

### 2. `.md` 파일 저장 형식 변경 (`manuals.py`)

**현재**
```markdown
- 안전복장 미착용인가?
- 구명복을 착용하지 않았는가?
```

**변경 후**
```markdown
[PPE_MISSING] 안전복장 미착용인가?
[PPE_MISSING] 구명복을 착용하지 않았는가?
[ACCESS_VIOLATION] 크레인 작업반경 내 무단출입인가?
```

categories가 전달되지 않으면 기존 형식(`- 항목`) 유지.

---

### 3. API 스키마 변경 (`manuals.py`)

**`/manuals/analyze` 응답 추가 필드**
```json
{
  "session_id": "...",
  "static": [...],
  "dynamic": [...],
  "static_categories": [
    {"code": "PPE_MISSING", "label": "보호장비 미착용", "items": [...]}
  ],
  "dynamic_categories": [...],
  "zones": [...]
}
```

**`ConfirmRequest` 스키마 추가**
```python
class CategoryItem(BaseModel):
    code: str
    label: str
    items: list[str]

class ConfirmRequest(BaseModel):
    session_id: str
    static: list[str]
    dynamic: list[str]
    static_categories: list[CategoryItem] = []   # 신규, 선택값
    dynamic_categories: list[CategoryItem] = []  # 신규, 선택값
    zones: list[ZoneChecklist] = []
```

---

### 4. VLM 프롬프트 템플릿 변경 (`static_prompt.j2`, `dynamic_prompt.j2`)

**현재**
```
"anomaly_type": "stacking" | "blocked_path" | "damaged_facility" | "equipment_issue" | "normal"
```

**변경 후**
```
위 체크리스트에서 [코드] 태그가 이상 유형 분류 기준이다.
이상 감지 시 해당 항목의 코드를 anomaly_type에 그대로 출력하라.

"anomaly_type": 체크리스트 [코드] 중 하나 | "normal"
```

---

## 변경 파일 목록

| 파일 | 변경 내용 | 변경 규모 |
|------|-----------|-----------|
| `services/backend/app/api/agent/checklist_agent.py` | `normalize_categories()` 추가 | 소 |
| `services/backend/app/api/manuals.py` | `/analyze` 응답, `/confirm` 저장, 스키마 변경 | 중 |
| `services/inference/prompts/static_prompt.j2` | anomaly_type 안내 문구 수정 | 소 |
| `services/inference/prompts/dynamic_prompt.j2` | anomaly_type 안내 문구 수정 | 소 |

**변경 없는 파일**: `vlm/client.py`, `worker.py`, DB 모델, 프론트엔드, `slack.py`

---

## 하위 호환

- `static_categories` / `dynamic_categories` 미전달 시 기존 `.md` 형식(`- 항목`) 유지
- `.j2` 템플릿은 체크리스트에 `[코드]` 태그가 없어도 동작 (VLM이 "normal" 또는 기존 방식으로 출력)
