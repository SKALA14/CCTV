# VLM 기반 AI CCTV 분석 시스템

외부 VMS(Video Management System)가 관리하는 CCTV 스트림을 받아 YOLO + VLM으로 이상 상황을 탐지·요약하고,
대시보드에서 실시간 모니터링하는 AI 분석 시스템.

> **설계 전제**: 영상 원본 보관·관리는 외부 VMS 책임. 본 시스템은 분석만 담당.

---

## 전체 데이터 흐름

```
[외부 VMS / mediamtx RTSP 시뮬레이터 / 로컬 파일]
    │
    │  RTSP pull  또는  로컬 파일 읽기
    ▼
[ingestion service]  ×4 (cam0~cam3)
    │  프레임 샘플링 (FPS 기반)
    │  프레임 → 로컬 볼륨 저장, 경로만 메시지에 포함
    ▼
Redis Streams : frames
    │
    ▼
[inference service]
    ├── emergency pipeline : YOLO (화재·낙상) → 즉시 alerts 발행
    ├── dynamic pipeline   : Dual-EMA Trigger 변화 감지 → VLM 분석
    └── static pipeline    : 정기 VLM 분석 (침입·PPE 등)
    ▼
Redis Streams : events  /  alerts
    │
    ▼
[backend service]
    ├── worker  : Redis events·alerts 구독 → PostgreSQL 저장 (pgvector 임베딩 포함)
    └── API     : REST (이벤트 조회·시맨틱 검색·채널·매뉴얼) + WebSocket (실시간 푸시)
    │
    ▼
[notification service]
    │  alerts·events 구독 → Slack Webhook 발송
    │
[frontend dashboard]
    DashboardView / SearchView / ManualView
```

---

## 디렉토리 구조

```
CCTV/
│
├── services/
│   ├── ingestion/                   # 영상 수집 · 프레임 샘플링 서비스
│   │   ├── app/
│   │   │   ├── main.py
│   │   │   ├── config.py
│   │   │   ├── sampler.py
│   │   │   ├── publisher.py
│   │   │   ├── redis_client.py
│   │   │   └── sources/
│   │   │       ├── base.py          # FrameSource ABC
│   │   │       ├── file.py          # 로컬 파일 소스
│   │   │       ├── rtsp.py          # RTSP 소스
│   │   │       └── youtube.py       # YouTube 소스
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   │
│   ├── inference/                   # YOLO + VLM 추론 파이프라인 서비스
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── redis_client.py
│   │   ├── schema.py
│   │   ├── emergency/               # 화재·낙상 즉시 감지 → alerts 발행
│   │   │   ├── fire_worker.py
│   │   │   ├── pose_worker.py
│   │   │   ├── aggregator.py
│   │   │   └── process.py
│   │   ├── dynamic/                 # Dual-EMA Trigger 기반 변화 감지 → VLM 분석
│   │   │   ├── buffer.py
│   │   │   ├── optical_flow.py      # FrameFeatureExtractor (시각 feature 추출)
│   │   │   ├── trigger.py           # RealtimeTriggerSelector (Dual-EMA)
│   │   │   ├── vlm_worker.py
│   │   │   └── process.py
│   │   ├── static/                  # 정기 VLM 분석 (침입·PPE 등)
│   │   │   ├── vlm_worker.py
│   │   │   └── process.py
│   │   ├── cleaner/                 # 처리 완료 프레임 파일 정리
│   │   │   └── process.py
│   │   ├── models/                  # YOLO 모델 래퍼
│   │   │   ├── fire.py              # 화재·연기 감지 (fire_smoke.pt)
│   │   │   ├── pose.py              # 낙상 감지 (yolo26m-pose.pt)
│   │   │   └── common.py
│   │   ├── vlm/
│   │   │   └── client.py            # OpenAI Vision API 클라이언트
│   │   ├── prompts/
│   │   │   ├── dynamic_prompt.j2
│   │   │   └── static_prompt.j2
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   │
│   ├── backend/                     # REST API + WebSocket + DB 워커 서비스
│   │   ├── app/
│   │   │   ├── main.py
│   │   │   ├── config.py
│   │   │   ├── worker.py            # Redis events·alerts 구독 → 임베딩 → PostgreSQL 저장
│   │   │   ├── db/
│   │   │   │   ├── models.py        # Site, User, CctvChannel, EventLog (pgvector 임베딩)
│   │   │   │   └── session.py
│   │   │   └── api/
│   │   │       ├── auth.py          # 로그인·로그아웃·세션 (JWT 쿠키)
│   │   │       ├── sites.py         # 현장 조회
│   │   │       ├── users.py         # 계정 CRUD·비밀번호 변경
│   │   │       ├── events.py        # 이벤트 조회 + 시맨틱 검색
│   │   │       ├── channels.py      # 채널 CRUD + per-camera 지시문
│   │   │       ├── manuals.py       # 매뉴얼 PDF 업로드·체크리스트 관리
│   │   │       ├── status.py        # 운영 현황 (admin)
│   │   │       ├── reports.py       # 안전 이벤트 집계 (admin)
│   │   │       ├── ws.py            # WebSocket 실시간 푸시
│   │   │       ├── checklist_store.py  # 현장별 체크리스트 저장/로드
│   │   │       ├── deps.py             # 인증·권한 의존성
│   │   │       ├── embed_describer.py  # 이벤트 설명 임베딩 생성
│   │   │       ├── query_expander.py   # 검색 쿼리 확장 (LLM)
│   │   │       ├── time_parser.py      # 자연어 시간 파싱
│   │   │       ├── schemas.py
│   │   │       └── agent/
│   │   │           ├── pdf_parser.py       # PDF 텍스트 추출
│   │   │           ├── checklist_agent.py  # 체크리스트 생성 AI 에이전트
│   │   │           └── instruction_agent.py
│   │   ├── prompts/                 # 현장별 체크리스트(checklist.json)·구역 저장
│   │   │   └── {site_id}/
│   │   ├── tests/
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   │
│   ├── frontend/                    # Vue 3 대시보드
│   │   ├── src/
│   │   │   ├── views/
│   │   │   │   ├── DashboardView.vue   # 실시간 채널 모니터링
│   │   │   │   ├── SearchView.vue      # 시맨틱 이벤트 검색
│   │   │   │   ├── ManualView.vue      # 매뉴얼 체크리스트 관리
│   │   │   │   └── ClipDetailView.vue
│   │   │   ├── components/
│   │   │   │   ├── dashboard/          # ChannelCard, ChannelGrid, EventToast 등
│   │   │   │   ├── search/             # SearchBar, ResultCard, ClipDetail 등
│   │   │   │   ├── manual/             # ChecklistItem, ChecklistReview
│   │   │   │   └── layout/             # AppHeader, AppNav
│   │   │   ├── stores/                 # Pinia (channelStore, eventStore, manualStore)
│   │   │   ├── composables/            # useWebSocket, useWebRTC, useEvents 등
│   │   │   ├── api/                    # axios 클라이언트 (events, channels, manuals)
│   │   │   ├── constants/
│   │   │   └── router/
│   │   ├── Dockerfile
│   │   ├── nginx.conf
│   │   └── package.json
│   │
│   └── notification/                # Slack 알림 발송 서비스
│       ├── main.py
│       ├── slack.py                 # alerts·events 구독 → Slack Webhook
│       └── Dockerfile
│
├── infra/
│   ├── docker-compose.yaml          # 전체 스택 기동
│   └── mediamtx.yml                 # RTSP 시뮬레이터 설정
│
├── frames/                          # 샘플링된 프레임 저장 볼륨
├── sample/                          # 테스트용 영상 파일 (fall.mp4, fire.mp4 등)
├── scripts/                         # 유틸 스크립트 (list_models.py, test_prompt.py)
└── README.md
```

---

## 기술 스택

| 영역 | 기술 |
|------|------|
| Ingestion | Python, OpenCV, redis-py |
| Inference | Python, Ultralytics YOLO, OpenAI Vision API, Jinja2, PyTorch |
| Backend | FastAPI, SQLAlchemy (async), PostgreSQL + pgvector, redis-py, OpenAI API |
| Frontend | Vue 3, Pinia, Vue Router, TailwindCSS, Vite |
| Broker | Redis Streams (`frames`, `events`, `alerts` 채널) |
| Storage | 로컬 볼륨 (MVP) |
| RTSP 시뮬레이터 | mediamtx (WebRTC / RTSP / HLS) |
| Infra | Docker, docker-compose |

---

## 주요 기능

| 기능 | 설명 |
|------|------|
| 멀티 카메라 수집 | cam0~cam3 독립 ingestion 컨테이너, RTSP·파일·YouTube 소스 지원 |
| 이중 YOLO 파이프라인 | 화재·연기(fire_smoke.pt) + 낙상(yolo26m-pose) 긴급 감지 후 즉시 alerts 발행 |
| Dynamic / Static VLM | Dual-EMA Trigger로 변화 감지 → VLM 분석 / 정기 VLM 분석 병렬 운용 |
| 시맨틱 검색 | 이벤트 설명 OpenAI 임베딩(1536d) → pgvector 유사도 검색 |
| 매뉴얼 AI 에이전트 | PDF 업로드 → 체크리스트 자동 생성·정제 (checklist_agent) |
| 실시간 WebSocket | 이벤트 발생 즉시 대시보드 푸시, 10초 사건 갭으로 중복 알림 억제 |
| Slack 알림 | 긴급(alerts)·일반(events) 이벤트 → Slack Webhook 자동 발송 |

---

## 빠른 시작

```bash
# 1. 환경변수 설정
cp infra/.env.example infra/.env
# infra/.env에 OPENAI_API_KEY, AUTH_SECRET, ADMIN_PASSWORD 입력 (필수)
# SLACK_WEBHOOK_URL은 선택 (미설정 시 Slack 알림만 skip)
# ※ AUTH_SECRET·ADMIN_PASSWORD 미설정 시 backend가 기동을 거부함

# 2. 테스트 영상을 sample/ 디렉토리에 준비 (fall.mp4, fire.mp4 등)

# 3. 전체 스택 기동
docker compose -f infra/docker-compose.yaml up -d

# 4. 대시보드 접속
open http://localhost
# Backend API
open http://localhost:8000/docs
```

---

## 서비스별 상세 문서

- [ingestion README](services/ingestion/README.md)
- [inference README](services/inference/README.md)
- [backend README](services/backend/README.md)
- [frontend README](services/frontend/README.md)
- [notification README](services/notification/README.md)
- [infra README](infra/README.md)
