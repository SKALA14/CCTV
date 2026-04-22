# backend 서비스

## 역할
Redis Streams `events` 채널을 구독해 분석 결과를 PostgreSQL에 저장하고,
프론트엔드 대시보드에 REST API와 WebSocket을 제공한다.

## 데이터 흐름
```
Redis Streams : events
    │
    ├── worker.py (백그라운드 태스크)
    │       └── PostgreSQL INSERT
    │
    └── ws.py (WebSocket)
            └── 실시간 클라이언트 푸시

프론트엔드 ──REST──▶ routes/events.py ──▶ PostgreSQL SELECT
```

## API 엔드포인트
| 메서드 | 경로 | 설명 |
|--------|------|------|
| GET | `/api/v1/events` | 이벤트 목록 조회 (필터·페이지네이션) |
| GET | `/api/v1/events/{id}` | 이벤트 단건 조회 |
| GET | `/api/v1/cameras` | 카메라 목록 조회 |
| WS  | `/ws/events` | 실시간 이벤트 푸시 |
| GET | `/health` | 헬스체크 |

## 핵심 설계 포인트
- FastAPI `lifespan`에서 `worker.py`를 백그라운드 태스크로 시작. API 서버와 워커가 한 프로세스에서 동작.
- DB 테이블은 시작 시 `Base.metadata.create_all`로 자동 생성 (MVP). 추후 Alembic 마이그레이션으로 전환.
- WebSocket은 Redis Stream을 `$`(현재 시점 이후)부터 읽어 신규 이벤트만 클라이언트에 푸시.

## 환경변수
| 변수 | 기본값 | 설명 |
|------|--------|------|
| `DATABASE_URL` | `postgresql+asyncpg://cctv:cctv@postgres:5432/cctv` | DB 연결 URL |
| `REDIS_URL` | `redis://redis:6379` | Redis 연결 URL |
| `CORS_ORIGINS` | `["http://localhost:3000"]` | 허용 CORS 출처 |
