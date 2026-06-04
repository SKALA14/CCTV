# infra

Docker Compose 기반 전체 스택 구성.

---

## 컨테이너 구성

| 컨테이너 | 이미지 / 빌드 | 포트 | 설명 |
|---------|-------------|------|------|
| `redis` | redis:7-alpine | 6379 | Redis Streams 브로커 |
| `postgres` | pgvector/pgvector:pg16 | 5432 | 이벤트 저장 + 벡터 검색 DB |
| `mediamtx` | bluenviron/mediamtx | 8554(RTSP) 8888(HLS) 8889(WebRTC) 9997(API) | RTSP 재스트림·WebRTC 릴레이 |
| `ingestion_0~3` | services/ingestion | — | 카메라별 독립 프레임 수집 (cam0~cam3) |
| `inference` | services/inference | — | YOLO + VLM 추론 파이프라인 |
| `backend` | services/backend | 8000 | REST API + WebSocket + DB 워커 |
| `notification` | services/notification | — | Slack 알림 발송 |
| `frontend` | services/frontend | 80 | Vue 3 대시보드 (nginx) |

---

## 볼륨 공유

| 볼륨 경로 | 공유 컨테이너 | 설명 |
|----------|-------------|------|
| `../frames` → `/frames` | ingestion, inference, backend, frontend | 샘플링된 프레임 + 스냅샷 저장 |
| `../sample` → `/sample` | ingestion, frontend | 테스트용 영상 파일 |
| `../services/backend/prompts` → `/prompts` (inference) / `/service/prompts` (backend) | inference, backend | 체크리스트 파일 공유. backend가 쓰면 inference가 즉시 읽음 |

---

## 환경변수 설정

```bash
cp .env.example .env
# .env 편집: OPENAI_API_KEY, SLACK_WEBHOOK_URL 입력
```

| 변수 | 설명 |
|------|------|
| `OPENAI_API_KEY` | inference VLM 호출 + backend 임베딩·체크리스트 분석 |
| `OPENAI_MODEL` | 기본 `gpt-4o` |
| `SLACK_WEBHOOK_URL` | Slack 알림 수신 Webhook URL |

---

## 실행

```bash
# 전체 스택 기동
docker compose -f infra/docker-compose.yaml up -d

# 로그 확인
docker compose -f infra/docker-compose.yaml logs -f inference
docker compose -f infra/docker-compose.yaml logs -f backend

# 중단
docker compose -f infra/docker-compose.yaml down
```

기동 후 접속:
- 대시보드: http://localhost
- Backend API 문서: http://localhost:8000/docs
- mediamtx 관리 API: http://localhost:9997

---

## mediamtx 역할

외부 RTSP 카메라를 등록하면 mediamtx가 재스트림하고, ingestion은 `rtsp://mediamtx:8554/{channelName}`을 단일 소비자로 읽는다.
카메라 직접 접속 대신 mediamtx를 경유해 **카메라 이중 접속 문제를 방지**한다.

브라우저 웹캠 스트림은 WHIP(WebRTC HTTP Ingest Protocol)으로 mediamtx에 push하고 ingestion이 RTSP로 재수신한다.

---

## 로컬 개발 팁

특정 서비스만 빌드:
```bash
docker compose -f infra/docker-compose.yaml build inference
docker compose -f infra/docker-compose.yaml up -d --no-deps inference
```

체크리스트 파일 직접 확인:
```bash
ls services/backend/prompts/
# static_checklist.md, dynamic_checklist.md, zone_*.md 등
```
