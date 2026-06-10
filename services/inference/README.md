# Inference Service

CCTV 프레임을 YOLO + VLM으로 분석해 이상 이벤트를 Redis에 발행하는 서비스.

---

## 프로세스 구조

```
main.py
  ├── emergency  (Process)   # FireYOLO + PoseYOLO → alerts stream
  ├── dynamic    (Process)   # Optical Flow → VLM → events stream
  ├── static     (Process)   # 주기적 스냅샷 VLM → events stream
  └── cleaner    (Process)   # 처리 완료 프레임 파일 삭제
```

emergency 프로세스 내부에서 스레드로 동작하는 워커:

```
emergency (Process)
  ├── fire-thread   (Thread)  # FireYOLO  → result_queue
  └── pose-thread   (Thread)  # PoseYOLO  → result_queue
```

dynamic 프로세스 내부:

```
dynamic (Process)
  └── dynamic-vlm-thread  (Thread)  # VLMClient → events stream
```

---

## 프레임 처리 흐름

### Emergency 트랙

```
Redis frames stream (EMERGENCY_GROUP)
        │
        │ xreadgroup (block=100ms, count=10)
        ▼
[emergency/process] FrameJob 생성
        │
        │ fan-out (put_nowait)
        ├─────────────────────┐
        ▼                     ▼
  fire-thread           pose-thread
  (FireYOLO)            (PoseYOLO)
        │                     │
        └──── result_queue ───┘
                   │
          [aggregator] drain_results
                   │ msg_id 기준 결과 누적
                   │
          [aggregator] finalize_ready_frames
           (모든 모델 완료 or timeout → ACK)
                   │
          ┌────────┴────────┐
          │ fire / smoke    │ fallen
          ▼                 ▼
   FIRE_DEDUP_SEC      FALL_WINDOW_SEC 내
   쿨다운 체크         FALL_MIN_FRAMES 누적 체크
          │                 │
          └────── alerts stream ──────┘
```

### Dynamic 트랙

```
Redis frames stream (DYNAMIC_GROUP)
        │
        │ xreadgroup (block=100ms, count=1)
        ▼
[dynamic/process] Optical Flow 점수 계산
        │
        │ score < FLOW_THRESHOLD → ACK 후 스킵
        ▼
  DynamicBuffer에 적재
        │
        │ GENERAL_WINDOW_SEC 경과 후 flush
        │ frames < GENERAL_MIN_FRAMES or cooldown → ACK 후 스킵
        ▼
  job_queue (최대 VLM_QUEUE_SIZE=4)
        │
[dynamic-vlm-thread] VLM 분석
        │
        │ result == "normal" → 발행 생략
        ▼
  events stream
```

### Static 트랙

```
[static/process] asyncio 스케줄러 (STATIC_INTERVAL_SEC 주기)
        │
        │ Redis camera:*:source_url 스캔 → 활성 카메라 목록
        ▼
  카메라별 최신 JPEG 1장 선택
        │
        │ asyncio.gather (동시 호출)
        ▼
  VLM 분석 (static_prompt.j2)
        │
        │ result == "normal" → 발행 생략
        ▼
  events stream
```

---

## 핵심 타입 (schema.py)

| 타입 | 역할 |
|------|------|
| `FrameJob` | Redis msg_id·frame·카메라 정보를 담는 작업 단위 |
| `ModelResult` | 모델 worker가 result_queue로 반환하는 결과. `detections` 리스트 포함 |
| `PendingFrame` | msg_id별 진행 상태 추적. expected/received 모델 집합으로 완료 판단 |

detection 스키마:
```python
{
    "anomaly_type": str,   # fire / smoke / fallen / ...
    "danger_level": str,
    "description":  str,
    "confidence":   float,
    "source_model": str,
}
```

---

## 라우팅 분기

### emergency (즉시 발행 → alerts stream)
- `fire`, `smoke`: `FIRE_DEDUP_SEC` 내 동일 `(camera, type)` 중복 발행 억제
- `fallen`: camera별 `FALL_WINDOW_SEC` 내 `FALL_MIN_FRAMES` 이상 누적 시 발행 후 카운터 초기화

### dynamic (Optical Flow → VLM 검증 → events stream)
1. Optical Flow 점수가 `FLOW_THRESHOLD` 미만이면 무시
2. `GENERAL_WINDOW_SEC` 윈도우 만료 시 `GENERAL_MIN_FRAMES` 미달 또는 쿨다운 중이면 스킵
3. 조건 충족 시 최대 `GENERAL_BUFFER_SIZE`장을 VLM에 전달
4. VLM이 `normal`로 판정하면 발행 생략, 이상이면 `events` stream에 XADD

### static (주기 스냅샷 → VLM 검증 → events stream)
- `STATIC_INTERVAL_SEC`마다 활성 카메라 전체 스캔
- 카메라별 최신 JPEG 1장으로 VLM 호출, 이상이면 `events` stream에 XADD

---

## 주요 설정값 (config.py)

| 설정 | 기본값 | 설명 |
|------|--------|------|
| `FRAME_RESULT_TIMEOUT_SEC` | 5.0s | 모든 모델 결과 대기 최대 시간 |
| `FIRE_DEDUP_SEC` | 2.0s | fire/smoke 동일 카메라·타입 중복 발행 억제 시간 |
| `FALL_MIN_FRAMES` | 3 | 낙상 판정 최소 누적 프레임 수 |
| `FALL_WINDOW_SEC` | 5.0s | 낙상 누적 시간 윈도우 |
| `FLOW_THRESHOLD` | 500.0 | Optical Flow 최소 점수 (미달 시 dynamic 스킵) |
| `GENERAL_WINDOW_SEC` | 10.0s | dynamic 후보 수집 윈도우 |
| `GENERAL_MIN_FRAMES` | 3 | VLM 호출 최소 프레임 수 |
| `GENERAL_BUFFER_SIZE` | 5 | VLM에 전달하는 최대 프레임 수 |
| `GENERAL_MIN_CALL_INTERVAL` | 30.0s | camera별 VLM 호출 최소 간격 (쿨다운) |
| `STATIC_INTERVAL_SEC` | 1800.0s | static 스캔 주기 |
| `MODEL_QUEUE_SIZE` | 30 | 모델별 입력 큐 최대 크기 |
| `RESULT_QUEUE_SIZE` | 90 | 결과 큐 최대 크기 |

---

## Redis 인터페이스

| 방향 | 키 / 스트림 | 내용 |
|------|------------|------|
| 입력 | `frames` stream | `{frame_path, camera_id, timestamp}` |
| 출력 | `alerts` stream | emergency 이벤트 (fire·smoke·fallen) |
| 출력 | `events` stream | dynamic·static 이벤트 (VLM 검증 후) |
| 읽기 | `camera:*:source_url` | 활성 카메라 목록 (static 트랙) |
| 읽기 | `camera_instruction:{camera_id}` | 카메라별 추가 VLM 지시 |

---

## 실행

```bash
python main.py
```

모델 파일(`models/fire.pt`, `models/yolo26m-pose.pt`)이 실행 디렉토리 기준으로 존재해야 합니다.
