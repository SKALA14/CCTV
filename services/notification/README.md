# notification 서비스

## 역할
Redis Streams `alerts`(긴급)·`events`(일반) 두 채널을 Consumer Group으로 구독해,
이상 상황을 Slack Block Kit 메시지로 변환한 뒤 Webhook으로 전송한다.

## 데이터 흐름
```
Redis Streams : alerts / events
    │  xreadgroup (CONSUMER_GROUP="notification", count=10, block=1s)
    ▼
[main._consume]
    ├── alerts → send_emergency_alert  (🚨 긴급 상황 감지)
    └── events → send_general_alert    (이상 상황 감지 알림)
    │
    │  dedup 통과 시에만 전송
    ▼
Slack Webhook (POST, 응답 "ok" 확인)
```

## 핵심 설계 포인트
- `alerts`는 YOLO 긴급(fire·smoke·fallen), `events`는 VLM 일반 이상으로 분기 처리.
- **중복 억제(dedup)**: 같은 `(camera_id, event_type)` 알림이 `INCIDENT_GAP_SEC`(기본 10초, compose는 30초) 안에 다시 오면 같은 사건으로 보고 skip. `smoke`는 `fire`로 정규화해 화재·연기를 한 사건으로 묶는다.
- 일반 알림은 `anomaly_type`이 있고 `normal`이 아닐 때만 전송(`should_notify_general`).
- 한 건 전송 실패가 루프를 끊지 않도록 예외는 로깅만 하고 다음 메시지로 진행(해당 메시지는 xack 생략 → 재처리 대상).
- `SLACK_WEBHOOK_URL` 미설정 시 전송을 skip(경고 로그만). 알림 없이도 서비스는 정상 기동.

## 환경변수
| 변수 | 기본값 | 설명 |
|------|--------|------|
| `REDIS_URL` | (필수) | Redis 연결 URL |
| `SLACK_WEBHOOK_URL` | `""` | Slack Incoming Webhook URL. 비우면 전송 skip |
| `ALERTS_STREAM` | `alerts` | 긴급 알림 스트림 |
| `EVENTS_STREAM` | `events` | 일반 알림 스트림 |
| `INCIDENT_GAP_SEC` | `10` | 동일 사건 중복 억제 간격(초). compose 기본은 `30` |

## 실행
의존성은 `redis`, `requests` 두 개뿐이라 별도 `requirements.txt` 없이 Dockerfile에서 직접 설치한다.

```bash
cd services/notification
pip install redis requests
REDIS_URL=redis://localhost:6379 SLACK_WEBHOOK_URL=https://hooks.slack.com/... python main.py
```
