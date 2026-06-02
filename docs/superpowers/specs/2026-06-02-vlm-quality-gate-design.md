# VLM Detection Quality Gate Design

## Goal

Static/Dynamic VLM 파이프라인에 Confidence Gate + Cross-pipeline Dedup을 추가해 탐지 품질을 높이고 중복 이벤트를 억제한다. 모든 임계값은 config 기반으로 추후 확장 가능하게 설계한다.

## Architecture

VLM `_parse()` 결과가 anomaly일 때, 이벤트 발행 전에 두 단계 게이트를 통과시킨다.
게이트 로직은 `vlm/gate.py` 공통 모듈에 집약하여 Static/Dynamic 양쪽에서 동일하게 import한다.
Emergency(YOLO) 파이프라인은 게이트 대상이 아니다 — 실시간성이 핵심이고 자체 dedup(FIRE_DEDUP_SEC, FALL_MIN_FRAMES)이 이미 있다.

## Tech Stack

- Python 3.11, Redis (sync client from `redis_client.py`), pydantic-settings

---

## 1. Confidence Gate

### 동작

VLM이 `result="anomaly"` + `confidence < MIN_CONFIDENCE`를 반환하면 이벤트 발행을 억제한다.

- `result == "normal"` → Gate 없이 기존 동작 유지 (이벤트 발행 안 함)
- `result == "anomaly"` AND `confidence >= MIN_CONFIDENCE` → 발행 허용
- `result == "anomaly"` AND `confidence < MIN_CONFIDENCE` → **SUPPRESSED** (로그 기록, 이벤트 미발행)

### 설정

```python
# config.py
MIN_CONFIDENCE: float = 0.6  # env: MIN_CONFIDENCE
```

### 확장 포인트 (현재 미구현, 주석으로 명시)

```python
# Future: camera:{cam_id}:min_confidence Redis key로 카메라별 오버라이드
# Future: danger_level별 차등 임계값 (critical → 0.3, high → 0.5, low → 0.8)
```

### 로그 포맷

```
[static]  SUPPRESSED cam=cam0 confidence=0.45 threshold=0.60 danger=low type=SAFETY_BARRIERS
[dynamic] SUPPRESSED cam=cam1 confidence=0.38 threshold=0.60 danger=high type=PPE
```

---

## 2. Cross-pipeline Dedup

### 동작

어느 파이프라인이든 이벤트를 발행하면 Redis에 `event:dedup:{cam_id}` 키를 TTL로 설정한다. TTL 내에 다른(또는 같은) 파이프라인이 같은 카메라로 이벤트를 발행하려 하면 억제한다.

1. 이벤트 발행 직전: `GET event:dedup:{cam_id}`
2. 키 존재 → **DEDUP_HIT** 로그 후 억제
3. 키 없음 → 이벤트 발행 + `SETEX event:dedup:{cam_id} {TTL} {pipeline}`

### 설정

```python
# config.py
DEDUP_TTL_SEC: int = 60  # env: DEDUP_TTL_SEC
```

### Redis Key

```
event:dedup:{cam_id}    STRING    value="static"|"dynamic"    EX=DEDUP_TTL_SEC
```

### 확장 포인트 (현재 미구현, 주석으로 명시)

```python
# Future: danger_level == "critical" → dedup bypass (즉시 발행)
# Future: violated_index가 다르면 dedup 면제 (다른 체크리스트 항목 위반)
```

### 로그 포맷

```
[dynamic] DEDUP_HIT cam=cam0 already_fired_by=static ttl_remaining=42s
```

---

## 3. Gate 모듈 설계 (`vlm/gate.py`)

```python
def should_publish(result: dict, camera_id: str, pipeline: str) -> bool:
    """Confidence Gate + Dedup Check를 순차 적용.
    True면 이벤트 발행 허용, False면 억제.
    """
```

- Static worker: `analyze_camera()` 에서 `result["result"] == "anomaly"` 분기 진입 후, `xadd` 전에 `should_publish()` 호출
- Dynamic worker: `vlm_worker.run()` 에서 `result["result"] != "normal"` 분기 진입 후, `xadd` 전에 `should_publish()` 호출

### Dedup 키 설정 함수

```python
def mark_published(camera_id: str, pipeline: str) -> None:
    """이벤트 발행 후 dedup 키 설정."""
```

`should_publish()`와 `mark_published()`를 분리하는 이유: 발행 성공 후에만 dedup 키를 설정해야 한다 (xadd 실패 시 dedup이 걸리면 안 됨).

---

## 4. Dynamic Worker 특이사항

Dynamic VLM worker는 별도 **스레드**에서 실행된다 (`threading.Thread`). Redis sync client(`get_client()`)를 사용하므로 gate.py도 sync client를 사용해야 한다.

Static VLM worker는 **asyncio** 기반이지만 `run_in_executor`로 VLM 호출을 스레드에 위임한다. gate 호출 시점은 executor 밖(asyncio context)이므로 sync client 호출 시 `run_in_executor`로 감싸거나, gate를 async로 작성할 수 있다.

**결정: gate.py는 sync 함수로 작성한다.**
- Dynamic worker: 스레드에서 직접 호출
- Static worker: `analyze_camera()`에서 VLM 결과를 받은 후 sync 호출 (asyncio 이벤트 루프에서 blocking Redis 호출이지만, GET/SETEX는 sub-ms이므로 실질적 영향 없음)

---

## 5. 파일 변경 범위

| 파일 | 변경 내용 |
|------|-----------|
| `services/inference/config.py` | `MIN_CONFIDENCE`, `DEDUP_TTL_SEC` 추가 |
| `services/inference/vlm/gate.py` | **신규** — `should_publish()`, `mark_published()` |
| `services/inference/static/vlm_worker.py` | `analyze_camera()` 에 gate 호출 추가 |
| `services/inference/dynamic/vlm_worker.py` | `run()` 에 gate 호출 추가 |
| `services/inference/tests/test_gate.py` | **신규** — gate 단위 테스트 |

---

## 6. 적용 범위

| 파이프라인 | Confidence Gate | Cross-pipeline Dedup |
|:---:|:---:|:---:|
| Static (VLM) | O | O |
| Dynamic (VLM) | O | O |
| Emergency (YOLO) | X — 자체 dedup 존재 | X — alerts 스트림 별도 |

---

## 7. 타임라인 시나리오

```
t=0s   채널 등록 (cam0)
t=2s   Static VLM 호출 시작
t=8s   Static VLM 응답: anomaly, confidence=0.82
       → confidence_gate: 0.82 >= 0.60 → PASS
       → dedup_check: event:dedup:cam0 없음 → PASS
       → XADD events + SETEX event:dedup:cam0 "static" 60

t=22s  Dynamic VLM 응답: anomaly, confidence=0.71
       → confidence_gate: 0.71 >= 0.60 → PASS
       → dedup_check: event:dedup:cam0 존재 (TTL=46s) → DEDUP_HIT
       → 이벤트 억제됨

t=65s  event:dedup:cam0 만료
       → 이후 양쪽 파이프라인 모두 새 이벤트 발행 가능

t=90s  Static VLM 응답: anomaly, confidence=0.42
       → confidence_gate: 0.42 < 0.60 → SUPPRESSED
       → 이벤트 억제됨 (dedup check까지 안 감)
```
