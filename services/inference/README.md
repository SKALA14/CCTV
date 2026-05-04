```
main.py
  │
  ├── init_consumer_groups()       # redis_client.py
  │
  ├── Process(unified_pipeline)    # pipelines/s0_unified.py
  │     ├── s1_types.py            # 공통 작업/결과 타입
  │     ├── s2_ack.py              # XACK 및 프레임 처리 완료 표시
  │     ├── s3_annotation.py       # bbox 표시 저장
  │     ├── s4_model_worker.py     # 모델별 worker 실행
  │     ├── s5_emergency.py        # emergency 알림 발행
  │     ├── s6_general.py          # general 후보/VLM 윈도우 관리
  │     ├── s7_vlm_worker.py       # VLM 호출 및 events 발행
  │     ├── s8_aggregator.py       # msg_id 기준 결과 취합
  │     └── s9_cleaner.py          # 처리 완료 프레임 파일 삭제
  │
  └── models/
        ├── fire.py                # fire/smoke YOLO
        ├── pose.py                # fallen pose YOLO
        └── general.py             # VLM 후보 YOLO
```

## 현재 변경 사항

- `emergency.py`, `general.py`로 나뉘던 파이프라인을 `pipelines/unified.py`로 통합
- 상황별 YOLO 모델은 `models/fire.py`, `models/pose.py`, `models/general.py`로 분리
- 각 모델 worker는 시작 시 모델을 1회 로드한 뒤, 모델별 queue에서 FrameJob을 계속 처리
- 각 모델 결과에 `route` 필드를 포함하고, `route=emergency`는 즉시 `alerts`, `route=general`은 VLM 후보 버퍼로 분기
- aggregator는 Redis `msg_id` 기준으로 모델별 결과를 취합하고, 모든 모델 결과 도착 또는 timeout 후 ACK
- pipeline 내부 책임을 `s0_unified`부터 `s9_cleaner`까지 처리 순서가 보이도록 파일명에 순번을 붙여 분리
- cleaner는 ACK 이후 delete_queue에 등록된 프레임 파일을 삭제해 디스크 누적을 방지

## 실행 방법

`services/inference` 디렉토리에서 아래 명령으로 실행

```bash
python main.py
```

## 추후 변경 필요 사항

- VLM 입력 구조와 YOLO detection 출력 구조 통일
- downstream 모듈에서 바로 사용할 수 있도록 payload 스키마 확정

## 주의 사항

- 모델 파일 경로(`models/fire.pt`, `models/yolo26m-pose.pt`, `models/yolo26m.pt`)가 현재 작업 위치 기준으로 맞아야 함
- `route=emergency` 결과는 VLM을 기다리지 않고 즉시 알림으로 발행됨
- 모델별 처리 속도가 달라도 `msg_id` 기준으로 결과를 합치며, timeout이 지난 프레임은 도착한 결과만 반영하고 처리 종료함
- general 후보 프레임은 VLM 처리 또는 스킵 결정 후 ACK되므로, cleaner 삭제도 그 이후에 수행됨

## 문서 반영 원칙

- inference 디렉토리 내 구현/실행 방식이 바뀌면 이 README도 함께 업데이트
