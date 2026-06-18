# backend 서비스

## 역할
Redis Streams `events`·`alerts` 채널을 구독해 분석 결과를 PostgreSQL(pgvector)에 저장하고,
프론트엔드 대시보드에 REST API와 WebSocket을 제공한다.
인증(JWT 쿠키)·현장(site) 격리·채널/매뉴얼/체크리스트 관리·시맨틱 검색·리포트까지 담당하는 단일 FastAPI 앱이다.

## 데이터 흐름
```
Redis Streams : events / alerts
    │
    ├── worker.py (lifespan 백그라운드 태스크)
    │       ├── events  → 일반(VLM) 이벤트 처리
    │       ├── alerts  → 긴급(YOLO) 이벤트 처리
    │       └── 설명 임베딩(OpenAI) 생성 → PostgreSQL INSERT (pgvector)
    │
    └── ws.py (WebSocket /ws)
            └── 실시간 클라이언트 푸시 (현장별 필터)

프론트엔드 ──REST(/api)──▶ api/*.py ──▶ PostgreSQL
```

## 핵심 설계 포인트
- FastAPI `lifespan`에서 `worker.py`를 백그라운드 태스크로 시작. API 서버와 워커가 한 프로세스에서 동작.
- worker는 `events`·`alerts` 두 스트림을 Consumer Group으로 동시 소비하고, 이벤트 설명을 OpenAI 임베딩(1536d)으로 변환해 pgvector 컬럼에 저장.
- DB 테이블은 시작 시 `Base.metadata.create_all`로 자동 생성(MVP). 최초 기동 시 현장(site)과 admin 계정을 **seed**하고, 보안 필수값(`AUTH_SECRET`·`ADMIN_PASSWORD`) 미설정 시 기동을 거부.
- 모든 데이터(이벤트·채널·체크리스트·계정)는 **현장(site) 단위로 격리**된다. 계정 권한은 `user`(조회) / `admin`(관리) 2단계.
- WebSocket은 Redis Stream을 `$`(현재 시점 이후)부터 읽어 신규 이벤트만 푸시하며, JWT 쿠키로 인증.
- 매뉴얼 PDF는 LLM 에이전트(`api/agent/`)로 분석 → 구역별 체크리스트를 생성/정제/확정하고, 확정 결과는 현장별 `checklist.json`으로 저장(`PROMPTS_DIR`).

## REST API
모든 경로는 nginx가 `/api`로 프록시한다(아래는 백엔드 기준 경로). 인증은 httpOnly JWT 쿠키.

| 그룹 | 메서드·경로 | 설명 |
|------|------------|------|
| 인증 | `POST /auth/login` · `POST /auth/logout` · `GET /auth/me` | 로그인·로그아웃·내 정보 |
| 현장 | `GET /sites` · `GET /sites/{id}` | 현장 조회 (seed 전용, 읽기) |
| 계정 | `POST/GET/PATCH/DELETE /sites/{id}/users` | 현장 내 계정 CRUD (admin) |
| 계정 | `POST /sites/{id}/users/{uid}/reset-password` | 비밀번호 초기화 (admin) |
| 계정 | `PATCH /users/me/password` | 내 비밀번호 변경 |
| 이벤트 | `GET /events` | 목록 조회 (현장·채널·파이프라인·기간 필터, 페이지네이션) |
| 이벤트 | `GET /events/search` | 자연어 시맨틱 검색 (pgvector) |
| 이벤트 | `GET /events/{id}` | 단건 조회 |
| 채널 | `GET/POST /channels` · `PUT/DELETE /channels/{name}` | 채널 CRUD (소스 등록 → ingestion 트리거) |
| 채널 | `POST /channels/{cam}/instruction/analyze` · `PATCH .../confirm` | per-camera 감지 지시문 |
| 매뉴얼 | `POST /manuals/analyze` · `/refine` · `/confirm` · `/analyze-diff` · `/merge` | PDF 분석·체크리스트 생성/병합 |
| 매뉴얼 | `GET /manuals/checklist` · `POST/GET /manuals/zones` | 적용 체크리스트·구역 조회/등록 |
| 현황 | `GET /status/health · /overview · /devices · /accounts · /today-events` | 운영 현황 (admin) |
| 리포트 | `GET /reports/summary` | 안전 이벤트 집계 (admin) |
| WS | `WS /ws` | 실시간 이벤트 푸시 |

## 데이터 모델 (db/models.py)
| 테이블 | 클래스 | 설명 |
|--------|--------|------|
| `sites` | `Site` | 현장. 모든 데이터 격리 단위 |
| `users` | `User` | 계정 (role: user/admin, `must_change_password`, `site_id`) |
| `cctv_channels` | `CctvChannel` | 카메라 채널 (소스·mtxPath·구역) |
| `event_logs` | `EventLog` | 분석 이벤트 (설명 임베딩 pgvector 1536d 포함) |

## 환경변수
| 변수 | 기본값 | 설명 |
|------|--------|------|
| `DATABASE_URL` | `postgresql+asyncpg://cctv:cctv@postgres:5432/cctv` | DB 연결 URL |
| `REDIS_URL` | `redis://redis:6379` | Redis 연결 URL |
| `EVENTS_STREAM` / `ALERTS_STREAM` / `FRAMES_STREAM` | `events` / `alerts` / `frames` | Redis 스트림 이름 |
| `CORS_ORIGINS` | `["http://localhost:3000"]` | 허용 CORS 출처 |
| `OPENAI_API_KEY` | `""` | 임베딩·검색어 확장·체크리스트 에이전트용 (필수) |
| `PROMPTS_DIR` | `/service/prompts` | 현장별 체크리스트(`checklist.json`) 저장 위치 |
| `AUTH_SECRET` | `""` | JWT 서명 키 (필수 — 미설정 시 기동 거부) |
| `ADMIN_USERNAME` / `ADMIN_PASSWORD` | `admin` / `""` | 초기 admin seed (PASSWORD 필수) |
| `SITE_NAME` | `default` | 초기 현장 seed 이름 |
| `JWT_EXPIRE_HOURS` | `8` | 토큰 유효 시간 |
| `COOKIE_SECURE` | `false` | 운영 HTTPS 환경에서는 `true` |

## 실행
```bash
cd services/backend
python -m venv .venv && source .venv/bin/activate  # Python 3.11
pip install -r requirements.txt
cp ../../infra/.env.example .env   # AUTH_SECRET, ADMIN_PASSWORD, OPENAI_API_KEY 입력
uvicorn app.main:app --reload --port 8000
```

테스트:
```bash
pytest
```
