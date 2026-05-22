# Inference Service

CCTV 프레임을 YOLO + VLM으로 분석해 이상 이벤트를 Redis에 발행하는 서비스.

---

## 프로세스 구조

```
main.py
  ├── unified  (Process)   # s0_unified.py — 프레임 수신·분배·취합 메인 루프
  └── cleaner  (Process)   # s9_cleaner.py — 처리 완료 프레임 파일 삭제
```

unified 프로세스 내부에서 스레드로 동작하는 워커:

```
unified (Process)
  ├── fire-worker    (Thread)  # FireYOLO  → result_queue
  ├── pose-worker    (Thread)  # PoseYOLO  → result_queue
  ├── general-worker (Thread)  # GeneralYOLO → result_queue
  └── vlm-worker     (Thread)  # VLMClient → events stream
```

---

## 프레임 처리 흐름

```
Redis frames stream
        │
        │ xreadgroup (block=100ms, count=10)
        ▼
[s0_unified] FrameJob 생성
        │
        │ fan-out (put_nowait)
        ├──────────────────────────────────────────┐
        ▼                                          ▼
  fire-worker                              pose-worker   general-worker
  (FireYOLO.predict)                       (PoseYOLO)    (GeneralYOLO)
        │                                          │
        └──────────── result_queue ────────────────┘
                            │
                    [s8_aggregator] drain_results
                            │ msg_id 기준 결과 누적
                            │
                    [s8_aggregator] finalize_ready_frames
                      (모든 모델 완료 or timeout)
                            │
              ┌─────────────┴──────────────┐
              │ route=emergency             │ route=general
              ▼                            ▼
       [s5_emergency]               [s6_general] 버퍼에 적재
        fire/smoke → alerts stream          │
        fallen → 누적 후 alerts stream      │ GENERAL_WINDOW_SEC 경과 후
                                           ▼
                                    [s7_vlm_worker]
                                     VLM 분석
                                           │
                                    normal → 발행 생략
                                    이상   → events stream
                                           │
                                    ACK + delete_queue push
                                           │
                                    [s9_cleaner]
                                     JPEG 파일 삭제
```

---

## 핵심 타입 (s1_types.py)

| 타입 | 역할 |
|------|------|
| `FrameJob` | Redis msg_id·frame·카메라 정보를 담는 작업 단위. 모델 큐에 fan-out됨 |
| `ModelResult` | 모델 worker가 result_queue로 반환하는 결과. `detections` 리스트 포함 |
| `PendingFrame` | msg_id별 진행 상태 추적. expected/received 모델 집합으로 완료 판단 |

detection 스키마:
```python
{
    "route":        "emergency" | "general",
    "anomaly_type": str,   # fire / smoke / fallen / ...
    "danger_level": str,
    "description":  str,
    "confidence":   float,
    "source_model": str,
}
```

---

## 라우팅 분기

### emergency (즉시 발행)
- `fire`, `smoke`: 감지 즉시 `alerts` stream에 XADD
- `fallen`: camera별 시간 윈도우(`FALL_WINDOW_SEC`) 내 `FALL_MIN_FRAMES` 이상 누적 시 발행

### general (VLM 검증 후 발행)
1. GeneralYOLO가 일반 이상 후보를 탐지하면 camera별 버퍼에 적재
2. `GENERAL_WINDOW_SEC` 경과 후 `GENERAL_MIN_FRAMES` 미달이면 오탐으로 판정, ACK만 수행
3. 조건 충족 시 최대 `GENERAL_BUFFER_SIZE`장을 VLM에 전달
4. VLM이 `normal`로 판정하면 발행 생략, 이상으로 판정하면 `events` stream에 XADD

---

## 주요 설정값 (config.py)

| 설정 | 기본값 | 설명 |
|------|--------|------|
| `FRAME_RESULT_TIMEOUT_SEC` | 5.0s | 모든 모델 결과 대기 최대 시간 |
| `FALL_MIN_FRAMES` | 3 | 낙상 판정 최소 누적 프레임 수 |
| `FALL_WINDOW_SEC` | 5.0s | 낙상 누적 시간 윈도우 |
| `GENERAL_WINDOW_SEC` | 10.0s | general 후보 수집 윈도우 |
| `GENERAL_MIN_FRAMES` | 3 | VLM 호출 최소 프레임 수 |
| `GENERAL_BUFFER_SIZE` | 5 | VLM에 전달하는 최대 프레임 수 |
| `GENERAL_MIN_CALL_INTERVAL` | 30.0s | camera별 VLM 호출 최소 간격 (쿨다운) |
| `MODEL_QUEUE_SIZE` | 30 | 모델별 입력 큐 최대 크기 |
| `RESULT_QUEUE_SIZE` | 90 | 결과 큐 최대 크기 |

---

## Redis 인터페이스

| 방향 | 키 / 스트림 | 내용 |
|------|------------|------|
| 입력 | `frames` stream | `{frame_path, camera_id, timestamp}` |
| 출력 | `alerts` stream | emergency 이벤트 |
| 출력 | `events` stream | general 이벤트 (VLM 검증 후) |
| 내부 | `delete_queue` list | 삭제할 JPEG 경로. cleaner가 소비 |

---

## 실행

```bash
python main.py
```

모델 파일(`models/fire.pt`, `models/yolo26m-pose.pt`, `models/yolo26m.pt`)이 실행 디렉토리 기준으로 존재해야 합니다.
