# inference 서비스

CCTV 프레임을 YOLO + VLM으로 분석해 이상 이벤트를 Redis에 발행하는 서비스.

---

## 프로세스 구조

```
main.py
  ├── emergency  (Process)   # Fire/Pose YOLO → alerts stream
  ├── dynamic    (Process)   # Optical Flow → VLM → events stream
  ├── static     (Process)   # 주기 스냅샷 VLM → events stream
  └── cleaner    (Process)   # 처리 완료 프레임 파일 삭제
```

emergency 프로세스 내부 스레드:

```
emergency (Process)
  ├── fire-thread   # FireYOLO  → result_queue
  └── pose-thread   # PoseYOLO  → result_queue
```

---

## 파이프라인별 흐름

### Emergency 트랙 (YOLO → alerts stream)

```
Redis frames stream (EMERGENCY_GROUP)
        │  xreadgroup (block=100ms, count=10)
        ▼
[emergency/process] FrameJob 생성 → fan-out
        ├── fire-thread (FireYOLO, imgsz=320)
        └── pose-thread (PoseYOLO, imgsz=640)
                   │
          [aggregator] 모든 모델 완료 or FRAME_RESULT_TIMEOUT_SEC 초과 → ACK
                   │
          ┌────────┴────────┐
    fire/smoke            fallen
    FIRE_DEDUP_SEC        FALL_WINDOW_SEC 내
    쿨다운 체크           FALL_MIN_FRAMES 누적 체크
          │                    │
          └───── alerts stream ┘
```

낙상 판정은 점수제(score ≥ 2):
- torso 기울기 > `FALL_TORSO_ANGLE_THRESH`(45°): +2 (옆 낙상)
- 코 y좌표 > 엉덩이 y좌표: +2 (옆 낙상 보강)
- bbox 가로/세로 비 > `FALL_BBOX_RATIO_THRESH`(1.3): +1
- bbox 높이 급감 (최근 `FALL_HEIGHT_HISTORY_SEC`(3s) 최대 대비 50% 이하): +2 (정면 낙상)

### Dynamic 트랙 (Optical Flow → VLM → events stream)

```
Redis frames stream (DYNAMIC_GROUP)
        │  xreadgroup (block=100ms, count=1)
        ▼
[dynamic/process] Optical Flow 점수 계산
        │  score < FLOW_THRESHOLD → ACK 후 스킵
        ▼
  DynamicBuffer 적재
        │  GENERAL_WINDOW_SEC 경과 후 flush
        │  frames < GENERAL_MIN_FRAMES or 쿨다운 중 → ACK 후 스킵
        ▼
  job_queue (최대 VLM_QUEUE_SIZE=4)
        │
[dynamic-vlm-thread] render_prompt() → VLM 분석
        │
        │  Quality Gate 통과 시만 events stream 발행
        ▼
  events stream
```

### Static 트랙 (주기 스캔 → VLM → events stream)

```
[static/process] asyncio 스케줄러 (STATIC_INTERVAL_SEC 주기)
        │
        │  camera:registered pub/sub 수신 시 즉시 트리거 (신규 카메라)
        ▼
  Redis camera:*:source_url 스캔 → 활성 카메라 목록
        │  asyncio.gather — 카메라별 동시 호출
        ▼
  카메라별 최신 JPEG 1장 (등록 이후 프레임만 수락)
        │
[static/vlm_worker] render_prompt() → VLM 분석
        │
        │  Quality Gate 통과 시만 events stream 발행
        ▼
  events stream
```

---

## VLM Quality Gate (`vlm/gate.py`)

발행 전 두 단계 필터를 순차 적용한다.

1. **Confidence Gate**: `confidence < MIN_CONFIDENCE(0.6)` 이면 억제 (SUPPRESSED 로그)
2. **Cross-pipeline Dedup**: `event:dedup:{cam_id}` Redis 키로 Static↔Dynamic 중복 발행 `DEDUP_TTL_SEC(60s)` 차단

발행 성공 후 `mark_published()`로 dedup 키를 설정한다.

---

## 체크리스트 기반 VLM 프롬프트

`render_prompt(filename, camera_id)` 는 `(rendered_prompt, categories_dict)` 튜플을 반환한다.

- **글로벌 체크리스트**: `/prompts/{static,dynamic}_checklist.md` 파일 읽기 (backend와 볼륨 공유)
- **구역별 체크리스트**: `camera:{camera_id}:zone` Redis 키로 구역 확인 후 `zone_{safe_name}_{track}.md` 우선 적용
- **categories**: Redis `checklist:{track}:categories` hash에서 `{인덱스→카테고리 코드}` 조회
- VLM은 체크리스트 번호(`violated_index`)로 응답 → `categories` dict로 `anomaly_type` 코드 변환

---

## Redis 인터페이스

| 방향 | 키 / 스트림 | 내용 |
|------|------------|------|
| 읽기 | `frames` stream | `{frame_path, camera_id, timestamp}` |
| 쓰기 | `alerts` stream | emergency 이벤트 (fire·smoke·fallen) |
| 쓰기 | `events` stream | dynamic·static VLM 이벤트 |
| 읽기 | `camera:*:source_url` | 활성 카메라 목록 (static 트랙) |
| 읽기 | `camera:{id}:zone` | 카메라 구역명 (체크리스트 선택) |
| 읽기 | `camera_instruction:{id}` | 카메라별 추가 VLM 지시문 |
| 읽기 | `checklist:{track}:categories` | 체크리스트 인덱스→코드 매핑 hash |
| 구독 | `camera:registered` pub/sub | 신규 카메라 즉시 스캔 트리거 |
| 읽기/쓰기 | `event:dedup:{cam_id}` | Cross-pipeline 중복 발행 방지 |

---

## 주요 설정값

| 설정 | 기본값 | 설명 |
|------|--------|------|
| `YOLO_IMGSZ` | `320` | Fire YOLO 추론 해상도 (CPU 속도 우선) |
| `POSE_IMGSZ` | `640` | Pose YOLO 해상도 (키포인트 정밀도) |
| `FIRE_CONF` | `0.15` | Fire YOLO confidence 임계값 |
| `FIRE_DEDUP_SEC` | `2.0` | fire/smoke 동일 카메라·타입 중복 발행 억제 시간 |
| `FALL_TORSO_ANGLE_THRESH` | `45.0°` | 옆 낙상 torso 기울기 임계값 |
| `FALL_HEIGHT_DROP_RATIO` | `0.5` | 정면 낙상 높이 급감 비율 (최대 대비 50% 이하) |
| `FALL_HEIGHT_HISTORY_SEC` | `3.0` | 높이 비교 윈도우 |
| `FALL_MIN_FRAMES` | `3` | 낙상 판정 최소 누적 프레임 수 |
| `FALL_WINDOW_SEC` | `5.0` | 낙상 누적 시간 윈도우 |
| `FRAME_RESULT_TIMEOUT_SEC` | `30.0` | 모든 모델 결과 대기 최대 시간 |
| `MODEL_QUEUE_SIZE` | `10` | 모델별 입력 큐 최대 크기 |
| `FLOW_THRESHOLD` | `500.0` | Optical Flow 최소 점수 (미달 시 dynamic 스킵) |
| `GENERAL_WINDOW_SEC` | `10.0` | dynamic 후보 수집 윈도우 |
| `GENERAL_MIN_FRAMES` | `3` | VLM 호출 최소 프레임 수 |
| `GENERAL_BUFFER_SIZE` | `5` | VLM에 전달하는 최대 프레임 수 |
| `GENERAL_MIN_CALL_INTERVAL` | `30.0` | 카메라별 VLM 호출 최소 간격 |
| `STATIC_INTERVAL_SEC` | `1800.0` | static 정기 스캔 주기 |
| `MIN_CONFIDENCE` | `0.6` | VLM Quality Gate 신뢰도 임계값 |
| `DEDUP_TTL_SEC` | `60` | Cross-pipeline dedup 키 TTL |

---

## 실행

```bash
# 모델 파일이 services/inference/models/ 에 있어야 함
# - models/fire_smoke.pt
# - models/yolo26m-pose.pt
python main.py
```
