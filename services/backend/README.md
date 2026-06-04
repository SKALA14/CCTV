# backend 서비스

Redis Streams를 구독해 분석 결과를 PostgreSQL에 저장하고,
프론트엔드 대시보드에 REST API와 WebSocket을 제공한다.

---

## 역할 분담

| 스트림 | 처리 주체 | 설명 |
|--------|----------|------|
| `events` (VLM 결과) | backend worker | DB 저장 + 임베딩 생성 |
| `alerts` (YOLO 긴급) | ws.py + notification | WebSocket 푸시 + Slack 전용. **DB 저장 안 함** |

---

## 데이터 흐름

```
Redis : events stream (VLM 결과)
    │
    └── worker.py (백그라운드 asyncio task)
            ├── OpenAI Embeddings API → Vector(1536) 생성
            ├── 스냅샷 저장 (/frames/snapshots/{event_id}/*.jpg)
            └── PostgreSQL event_logs INSERT

Redis : alerts + events stream
    └── ws.py → WebSocket → 프론트엔드 실시간 푸시

프론트엔드 ──REST──▶ FastAPI ──▶ PostgreSQL
```

---

## 시작 시 초기화 (lifespan)

1. `PROMPTS_DIR`의 기존 체크리스트 파일 전체 삭제 (이전 세션 오염 방지)
2. PostgreSQL `vector` extension 활성화 + 테이블 자동 생성 + HNSW 인덱스 생성
3. `cctv_channels` 테이블에서 채널 목록 복구 → Redis `camera:{id}:source_url` 키 재설정
4. `run_worker()` asyncio task 시작

---

## API 엔드포인트

### 이벤트

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `GET` | `/events` | 이벤트 목록 조회. 인시던트 단위로 그룹핑해 반환 |
| `GET` | `/events/search?q=` | 자연어 시맨틱 검색 (쿼리 확장 + 임베딩 유사도) |
| `GET` | `/events/{event_id}` | 이벤트 단건 조회 |
| `WS` | `/ws` | 실시간 이벤트 푸시 (alerts + events 스트림 동시 구독) |

**이벤트 목록 쿼리 파라미터**: `channel_id`, `pipeline`, `event_type`, `danger_level`, `skip`, `limit`

**시맨틱 검색 동작**:
1. 자연어 시간 표현 파싱 ("어제 오후" → 시간 범위 추출)
2. 쿼리 자동 확장 (LLM으로 동의어·관련어 생성)
3. 각 확장 쿼리를 임베딩 후 pgvector 코사인 유사도 검색 (cosine distance < 0.65)
4. 인시던트 그룹핑 후 best distance 기준 정렬

### 채널

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `GET` | `/channels` | 채널 목록 조회 |
| `POST` | `/channels` | 채널 등록 (mediamtx 경로 등록 + Redis + PostgreSQL) |
| `PUT` | `/channels/{name}` | 채널 수정 |
| `DELETE` | `/channels/{name}` | 채널 삭제 |
| `POST` | `/channels/{camera_id}/instruction/analyze` | 채널별 자유 텍스트 → static/dynamic 체크리스트 초안 |
| `PATCH` | `/channels/{camera_id}/instruction/confirm` | 채널별 체크리스트 확정 → Redis `camera_instruction:{id}` 저장 |

채널 등록 시 소스 타입별 처리:
- `rtsp`: mediamtx에 경로 등록 → ingestion이 `rtsp://mediamtx:8554/{name}` 로 재수신
- `webcam`: mediamtx에 빈 경로 등록 → 브라우저 WHIP push 허용
- `file`: `/sample/{filename}` 경로 직접 설정

채널에 구역(`zone`)이 지정되면 `zones.json`에서 해당 구역의 비고(note)를 읽어 `camera_instruction:{cam_id}`에 자동 설정한다.

등록 완료 후 `camera:registered` pub/sub으로 inference static 프로세스에 즉시 스캔을 트리거한다.

### 매뉴얼 · 체크리스트

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `GET` | `/manuals` | 업로드된 매뉴얼 파일 메타데이터 목록 |
| `POST` | `/manuals` | 매뉴얼 파일 메타데이터 저장 (Redis) |
| `DELETE` | `/manuals/{id}` | 매뉴얼 파일 메타데이터 삭제 |
| `GET` | `/manuals/checklist` | 현재 글로벌 체크리스트 파일 내용 반환 |
| `POST` | `/manuals/analyze` | PDF 업로드 → LLM 체크리스트 분석 + 카테고리 정규화 |
| `POST` | `/manuals/refine` | 피드백 반영해 체크리스트 재생성 |
| `POST` | `/manuals/confirm` | 체크리스트 확정 → 파일 저장 + Redis categories hash 저장 |
| `POST` | `/manuals/zones` | 구역 CSV/XLSX 업로드 → `zones.json` 저장 |
| `GET` | `/manuals/zones` | 등록된 구역 이름 목록 반환 |

**체크리스트 저장 위치** (`PROMPTS_DIR = /service/prompts`):
- 글로벌: `static_checklist.md`, `dynamic_checklist.md`
- 구역별: `zone_{safe_name}_static.md`, `zone_{safe_name}_dynamic.md`
- inference 서비스와 동일 볼륨을 공유하므로 **저장 즉시 반영** (재시작 불필요)

**Redis categories hash** (`checklist:{track}:categories`):
- 체크리스트 번호 → 카테고리 코드 매핑 (`{"1": "PPE_MISSING", "2": "ACCESS_VIOLATION", ...}`)
- inference VLM이 `violated_index` 응답을 이 hash로 `anomaly_type` 코드로 변환

---

## DB 스키마

### `cctv_channels`

| 컬럼 | 타입 | 설명 |
|------|------|------|
| `camera_id` | PK String | `cam0` ~ `cam3` |
| `camera_name` | String | 사용자 지정 채널 이름 |
| `source_type` | String | `file` \| `rtsp` \| `webcam` |
| `source_url` | Text | ingestion이 실제 읽는 URL |
| `description` | Text | 채널 설명 (VLM 지시문 원본) |

### `event_logs`

| 컬럼 | 타입 | 설명 |
|------|------|------|
| `event_id` | UUID PK | |
| `camera_id` | String | 채널 삭제 후에도 이벤트 보존을 위해 FK 없음 |
| `camera_name` | String | 발생 시점의 채널 이름 스냅샷 |
| `pipeline` | String | `static` \| `dynamic` |
| `event_type` | String | 카테고리 코드 (e.g. `PPE_MISSING`) |
| `danger_level` | String | `critical` \| `high` \| `low` \| `none` |
| `description` | Text | VLM 설명 |
| `frame_path` | Text | 원본 프레임 경로 |
| `thumbnail_url` | Text | 대표 스냅샷 URL |
| `snapshot_urls` | JSON | 이벤트 전후 ±5s 스냅샷 URL 목록 (최대 5장) |
| `confidence` | Float | VLM 신뢰도 |
| `source_model` | String | |
| `occurred_at` | DateTime | |
| `embedding` | Vector(1536) | 시맨틱 검색용 임베딩. HNSW 인덱스 적용 |

---

## 인시던트 그룹핑

동일 `(camera_id, event_type)` 이벤트가 `INCIDENT_GAP_SEC(30s)` 이내로 연속 발생하면 하나의 인시던트로 묶는다.
대표 이벤트(가장 먼저 발생)와 건수·마지막 발생 시각을 함께 반환한다.
스냅샷은 인시던트 첫 이벤트에만 생성하고 후속은 skip해 디스크를 절약한다.

---

## 환경변수

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `DATABASE_URL` | `postgresql+asyncpg://cctv:cctv@postgres:5432/cctv` | PostgreSQL 연결 |
| `REDIS_URL` | `redis://redis:6379` | Redis 연결 |
| `EVENTS_STREAM` | `events` | VLM 이벤트 스트림 이름 |
| `ALERTS_STREAM` | `alerts` | YOLO 긴급 스트림 이름 |
| `INCIDENT_GAP_SEC` | `30.0` | 인시던트 그룹핑 간격 |
| `PROMPTS_DIR` | `/service/prompts` | 체크리스트 파일 저장 위치 |
| `OPENAI_API_KEY` | `""` | 임베딩·LLM 호출 키 |
| `OPENAI_MODEL` | `gpt-4o` | 체크리스트 분석·쿼리 확장 모델 |
| `FRAME_STORAGE_PATH` | `/frames` | 프레임 볼륨 루트 (스냅샷 저장) |
| `CORS_ORIGINS` | `["http://localhost:3000"]` | 허용 CORS 출처 |

---

## 실행 (로컬)

```bash
cd services/backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# PostgreSQL, Redis가 실행 중이어야 함
uvicorn app.main:app --reload --port 8000
# API 문서
open http://localhost:8000/docs
```
