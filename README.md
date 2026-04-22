# VLM 기반 AI CCTV 분석 시스템

외부 VMS(Video Management System)가 관리하는 CCTV 스트림을 받아 VLM으로 이상 상황을 탐지·요약하고,
대시보드에서 실시간 모니터링하는 AI 분석 시스템.

> **설계 전제**: 영상 원본 보관·관리는 외부 VMS 책임. 본 시스템은 분석만 담당.

---

## 전체 데이터 흐름

```
[외부 VMS / mediamtx RTSP 시뮬레이터 / 로컬 파일]
    │
    │  RTSP pull  또는  로컬 파일 읽기
    ▼
[ingestion service]
    │  프레임 샘플링 (FPS 기반)
    │  프레임 → 로컬 볼륨 저장, 경로만 메시지에 포함
    ▼
Redis Streams : frames
    │
    ▼
[inference service]
    │  프레임 경로 수신 → 이미지 로드 → VLM 호출 (OpenAI Vision API)
    │  분석 결과 (장면 설명, 이상 여부, 신뢰도)
    ▼
Redis Streams : events
    │
    ▼
[backend service]
    ├── worker  : Redis events 구독 → PostgreSQL 저장
    └── API     : REST (이벤트 조회) + WebSocket (실시간 푸시)
    │
    ▼
[frontend dashboard]
    LiveView / EventList / EventTimeline
```

---

## 디렉토리 구조

```
cctv-ai/
│
├── services/
│   ├── ingestion/                   # 영상 수집 · 프레임 샘플링 서비스
│   │   ├── app/
│   │   │   ├── main.py
│   │   │   ├── config.py
│   │   │   ├── sampler.py
│   │   │   ├── publisher.py
│   │   │   └── sources/
│   │   │       ├── base.py          # FrameSource ABC
│   │   │       └── file.py          # 로컬 파일 소스 (MVP)
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   └── README.md
│   │
│   ├── inference/                   # VLM 추론 파이프라인 서비스
│   │   ├── app/
│   │   │   ├── main.py
│   │   │   ├── config.py
│   │   │   ├── consumer.py
│   │   │   ├── vlm.py
│   │   │   └── publisher.py
│   │   ├── prompts/
│   │   │   └── scene_description.j2
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   └── README.md
│   │
│   ├── backend/                     # REST API + WebSocket + DB 워커 서비스
│   │   ├── app/
│   │   │   ├── main.py
│   │   │   ├── config.py
│   │   │   ├── db.py
│   │   │   ├── models.py
│   │   │   ├── schemas.py
│   │   │   ├── worker.py
│   │   │   └── routes/
│   │   │       ├── events.py
│   │   │       └── ws.py
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   └── README.md
│   │
│   └── frontend/                    # React 대시보드
│       ├── src/
│       │   ├── api/
│       │   ├── components/
│       │   └── hooks/
│       ├── Dockerfile
│       └── package.json
│
├── infra/
│   └── docker/
│       ├── docker-compose.yml       # 전체 스택 기동 (ingestion·inference·backend·frontend·redis·postgres·mediamtx)
│       └── .env.example
│
└── README.md
```

---

## 기술 스택

| 영역 | 기술 |
|------|------|
| Ingestion | Python, OpenCV, redis-py |
| Inference | Python, OpenAI Vision API, Jinja2 |
| Backend | FastAPI, SQLAlchemy (async), PostgreSQL, redis-py |
| Frontend | React, TypeScript, TailwindCSS |
| Broker | Redis Streams (`frames`, `events` 채널) |
| Storage | 로컬 볼륨 (MVP) |
| RTSP 시뮬레이터 | mediamtx |
| Infra | Docker, docker-compose |

---

## 빠른 시작

```bash
# 1. 환경변수 설정
cp infra/docker/.env.example infra/docker/.env
# .env에 OPENAI_API_KEY 입력

# 2. 테스트 영상을 data/ 디렉토리에 준비
mkdir -p data
# data/sample.mp4 배치

# 3. 전체 스택 기동
docker compose -f infra/docker/docker-compose.yml up -d

# 4. 대시보드 접속
open http://localhost:3000
```

---

## 서비스별 상세 문서

- [ingestion README](services/ingestion/README.md)
- [inference README](services/inference/README.md)
- [backend README](services/backend/README.md)
