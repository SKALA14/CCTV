# VLM 기반 AI CCTV 안전 분석 시스템

외부 CCTV 스트림을 받아 YOLO + VLM으로 이상 상황을 탐지·요약하고,
대시보드에서 실시간 모니터링하는 AI 분석 시스템.

> **설계 전제**: 영상 원본 보관·관리는 외부 VMS 책임. 본 시스템은 분석만 담당.

---

## 차별점

### 1. PDF 매뉴얼 → 구역별 맞춤 체크리스트 자동 생성

산업 안전 규정 PDF를 업로드하면 LLM이 **CCTV 화면에서 눈으로 직접 확인 가능한 항목만** 선별·정제하여 체크리스트를 생성한다.
소음·하중·수치·서류·인증 등 시각으로 확인 불가한 항목은 자동 제외된다.
작업 구역(고소 작업, 용접, 크레인 등)을 CSV/XLSX로 등록하면 구역별로 세분화된 체크리스트가 추가로 생성된다.

확정된 체크리스트는 backend와 inference가 동일 볼륨을 공유하므로, 저장 즉시 다음 VLM 호출부터 반영된다. **서비스 재시작 불필요.**

### 2. 3-Track 병렬 추론 파이프라인

| Track | 방식 | 목적 |
|-------|------|------|
| **Emergency** | YOLO (fire_smoke.pt + yolo26m-pose) | 화재·낙상 즉시 감지 → alerts 스트림 직행 |
| **Dynamic** | Optical Flow 변화 감지 → VLM | 움직임 감지 시에만 VLM 호출 (API 비용 절감) |
| **Static** | 주기적 VLM 스캔 | 정적 상태 위반 감지 (PPE 미착용·구역 표시·침입 등) |

Emergency는 즉각 응답이 필요하므로 YOLO로만 처리해 alerts 스트림으로 직행하고, VLM 분석 결과(events 스트림)와 경로를 완전히 분리한다.

### 3. VLM Quality Gate로 오탐 억제

VLM 발행 전 두 단계 필터를 적용한다:
- **Confidence Gate**: 신뢰도 < 0.6 이면 발행 억제
- **Cross-pipeline Dedup**: Static↔Dynamic 동일 카메라에서 60초 내 중복 발행 차단

### 4. 인시던트 그룹핑으로 알림 피로 감소

동일 카메라 + 동일 이벤트 타입이 30초 이내로 반복 발생하면 하나의 인시던트로 묶어 표시한다.
대시보드의 5분 쿨다운 알림과 결합해 알림 피로(alert fatigue)를 최소화한다.

### 5. 자연어 시맨틱 이벤트 검색

이벤트 설명을 OpenAI 임베딩(1536d)으로 저장하고, 검색 시 **쿼리 자동 확장** + **자연어 시간 파싱**을 거쳐 pgvector 유사도 검색을 수행한다.
"어제 오후 화재 관련 이슈" 같은 비정형 쿼리도 처리 가능하다.

---

## 전체 데이터 흐름

```
[외부 카메라 / RTSP 스트림 / 로컬 파일 / 웹캠]
    │
    │  mediamtx 재스트림 (RTSP·WebRTC)
    ▼
[ingestion service]  ×4 (cam0~cam3)
    │  프레임 샘플링 (2 FPS)
    │  /frames/{cam_id}/*.jpg 저장, 경로만 메시지에 포함
    ▼
Redis Streams : frames
    │
    ▼
[inference service]
    ├── emergency  : YOLO (화재·낙상) → alerts stream
    ├── dynamic    : Optical Flow 감지 → VLM → Quality Gate → events stream
    └── static     : 주기 스캔 + 신규 카메라 즉시 트리거 → VLM → Quality Gate → events stream
    │
    ▼
Redis Streams : events (VLM 결과)  /  alerts (YOLO 긴급)
    │                                       │
    ▼                                       ▼
[backend worker]                    [ws.py] + [notification service]
  events만 구독                       alerts + events 모두 구독
  임베딩 생성 → PostgreSQL INSERT     WebSocket 실시간 푸시 + Slack Webhook
  스냅샷 저장
    │
    ▼
[backend API]
  REST (이벤트·채널·매뉴얼·검색)
  WebSocket (/ws)
    │
    ▼
[frontend dashboard]
  DashboardView / SearchView / ManualView / ClipDetailView
```

---

## 기술 스택

| 영역 | 기술 |
|------|------|
| Ingestion | Python, OpenCV, redis-py |
| Inference | Python, Ultralytics YOLO, OpenAI Vision API (gpt-4o), Jinja2, PyTorch |
| Backend | FastAPI, SQLAlchemy (async), PostgreSQL + pgvector, redis-py, OpenAI API |
| Frontend | Vue 3, Pinia, Vue Router, TailwindCSS, Vite |
| Broker | Redis Streams (`frames` · `events` · `alerts`) |
| Storage | 로컬 볼륨 (프레임 + 스냅샷) |
| Proxy / RTSP | mediamtx (WebRTC · RTSP · HLS · WHIP) |
| Infra | Docker, docker-compose |

---

## 주요 기능

| 기능 | 설명 |
|------|------|
| 멀티 카메라 수집 | 독립 ingestion 컨테이너, RTSP·파일·YouTube·웹캠 소스 지원 |
| 화재 즉시 감지 | fire_smoke.pt YOLO — 탐지 시 2초 dedup 후 alerts 직행 |
| 낙상 즉시 감지 | yolo26m-pose — 점수제 판정 (옆 낙상 + 정면 낙상 높이 급감 탐지) |
| Dynamic VLM | Optical Flow로 움직임 감지 후 VLM 호출, 쿨다운으로 과호출 방지 |
| Static VLM | 구역별 체크리스트 기반 정기 상태 분석, 신규 카메라 등록 시 즉시 트리거 |
| VLM Quality Gate | 신뢰도 필터 + Cross-pipeline 60초 중복 차단 |
| 체크리스트 자동 생성 | PDF 업로드 → 시각 확인 가능 항목만 LLM 추출 → 카테고리 코드화 → 구역별 세분화 |
| 채널별 지시문 | 채널에 자유 텍스트 입력 → LLM이 static/dynamic 추가 지시문 생성 → VLM 프롬프트에 주입 |
| 인시던트 그룹핑 | 동일 카메라+이벤트 타입 연속 발생을 묶어 노이즈 감소 |
| 스냅샷 저장 | 이벤트 전후 ±5초 프레임 최대 5장 자동 수집 (인시던트 첫 이벤트에만) |
| 시맨틱 검색 | OpenAI 임베딩 + pgvector HNSW + 쿼리 자동 확장 + 자연어 시간 파싱 |
| 실시간 WebSocket | alerts + events 동시 구독, 5분 쿨다운 중복 알림 방지 |
| Slack 알림 | Emergency(alerts) → 즉시 알림 / VLM(events) → high 이상만 발송 |

---

## 디렉토리 구조

```
CCTV/
│
├── services/
│   ├── ingestion/                   # 영상 수집 · 프레임 샘플링
│   │   └── app/
│   │       ├── main.py              # 소스 대기 → FpsSampler → FramePublisher
│   │       ├── config.py
│   │       └── sources/             # FrameSource ABC (file / rtsp / youtube)
│   │
│   ├── inference/                   # YOLO + VLM 3-Track 추론 파이프라인
│   │   ├── main.py                  # 4개 프로세스 fork
│   │   ├── emergency/               # Fire/Pose YOLO → alerts stream
│   │   ├── dynamic/                 # Optical Flow → VLM → events stream
│   │   ├── static/                  # 주기 + 즉시 트리거 VLM → events stream
│   │   ├── cleaner/                 # 처리 완료 프레임 파일 삭제
│   │   ├── models/                  # YOLO 모델 래퍼 (fire.py, pose.py)
│   │   ├── vlm/
│   │   │   ├── client.py            # OpenAI Vision API + 체크리스트 프롬프트 렌더링
│   │   │   └── gate.py              # Quality Gate (신뢰도 필터 + cross-pipeline dedup)
│   │   └── prompts/                 # Jinja2 프롬프트 템플릿 (dynamic_prompt.j2, static_prompt.j2)
│   │
│   ├── backend/                     # REST API + WebSocket + DB 워커
│   │   └── app/
│   │       ├── main.py              # lifespan: DB 초기화 + 채널 복구 + worker 시작
│   │       ├── worker.py            # events stream 구독 → 임베딩 생성 → PostgreSQL INSERT
│   │       ├── db/
│   │       │   └── models.py        # CctvChannel, EventLog (Vector(1536))
│   │       └── api/
│   │           ├── events.py        # 이벤트 조회 + 인시던트 그룹핑 + 시맨틱 검색
│   │           ├── channels.py      # 채널 CRUD + mediamtx 연동 + instruction
│   │           ├── manuals.py       # PDF 분석 · 체크리스트 · 구역 등록
│   │           ├── ws.py            # WebSocket (alerts + events 실시간 푸시)
│   │           ├── query_expander.py   # 검색 쿼리 자동 확장 (LLM)
│   │           ├── time_parser.py      # 자연어 시간 파싱
│   │           └── agent/
│   │               ├── checklist_agent.py   # PDF → 체크리스트 생성·정제·카테고리 정규화
│   │               └── instruction_agent.py # 채널별 지시문 분석
│   │   └── prompts/                 # 체크리스트 파일 저장 위치 (inference와 볼륨 공유)
│   │
│   ├── frontend/                    # Vue 3 대시보드
│   │   └── src/
│   │       ├── views/               # DashboardView / SearchView / ManualView / ClipDetailView
│   │       ├── components/          # dashboard / search / manual / layout
│   │       ├── stores/              # Pinia (channelStore, eventStore, manualStore)
│   │       ├── composables/         # useWebSocket, useWebRTC, useEvents
│   │       └── api/                 # axios 클라이언트 (events, channels, manuals)
│   │
│   └── notification/                # Slack 알림 발송
│       ├── main.py                  # alerts + events 스트림 구독
│       └── slack.py                 # Emergency 즉시 알림 / VLM high 이상만 발송
│
├── infra/
│   ├── docker-compose.yaml          # 전체 스택 기동
│   └── mediamtx.yml                 # RTSP · WebRTC 릴레이 설정
│
├── frames/                          # 프레임 + 스냅샷 저장 볼륨
├── sample/                          # 테스트용 영상 파일
└── scripts/                         # 유틸 스크립트 (list_models.py, test_prompt.py 등)
```

---

## 빠른 시작

```bash
# 1. 환경변수 설정
cp infra/.env.example infra/.env
# infra/.env에 OPENAI_API_KEY, SLACK_WEBHOOK_URL 입력

# 2. 테스트 영상 준비 (fire.mp4 등)
# sample/ 디렉토리에 배치

# 3. inference 모델 파일 배치
# services/inference/models/fire_smoke.pt
# services/inference/models/yolo26m-pose.pt

# 4. 전체 스택 기동
docker compose -f infra/docker-compose.yaml up -d

# 5. 접속
open http://localhost           # 대시보드
open http://localhost:8000/docs # Backend API 문서
```

기동 후 대시보드에서 채널을 추가하면 ingestion이 자동으로 영상 수집을 시작한다.

---

## 임시 적용 사항

| 위치 | 내용 | 비고 |
|------|------|------|
| `services/frontend/src/stores/eventStore.js` | 동일 카메라 + 동일 이벤트 타입 알림 **5분 쿨다운** | 추후 별도 파일로 분리 예정 |

---

## 서비스별 상세 문서

- [ingestion README](services/ingestion/README.md)
- [inference README](services/inference/README.md)
- [backend README](services/backend/README.md)
- [frontend README](services/frontend/README.md)
- [infra README](infra/README.md)
