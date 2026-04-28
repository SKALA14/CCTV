```
main.py
  │
  ├── init_consumer_groups()       # redis_client.py
  │
  ├── Process(emergency_pipeline)  # pipelines/emergency.py
  │     └── models/yolo.py         # YOLO 추론
  │
  ├── Process(general_pipeline)    # pipelines/general.py
  │     ├── models/vlm.py          # GPT-4o 호출
  │     └── prompts/               # VLM 프롬프트 템플릿
  │
  └── Process(cleaner_process)     # cleaner.py
  ```

## 현재 변경 사항

- 현재 YOLO 관련 수정은 `services/inference/models/yolo.py` 기준으로 작업 중
- 아직 `main.py`와 연결되지 않았고, `yolo.py` 파일 단독 실행으로만 테스트 가능
- `EmergencyYOLO`, `GeneralYOLO` 추론 결과를 JSON 형태로 확인할 수 있도록 테스트 코드가 포함되어 있음

## 실행 방법

`services/inference` 디렉토리에서 아래 명령으로 실행

```bash
python models/yolo.py
```

테스트 이미지는 현재 `../../frames/video0/*.jpg` 경로를 기준으로 읽음

## 추후 변경 필요 사항

- `main.py` 또는 실제 pipeline 진입 경로와 `yolo.py` 연결
- VLM 입력 구조와 YOLO detection 출력 구조 통일
- downstream 모듈에서 바로 사용할 수 있도록 payload 스키마 확정

## 주의 사항

- 현재 테스트 코드는 `yolo.py`의 `__main__` 블록에서만 실행됨
- 모델 파일 경로(`models/fire.pt`, `models/yolo26m-pose.pt`, `models/yolo26m.pt`)가 현재 작업 위치 기준으로 맞아야 함
- 테스트 이미지 폴더가 없으면 추론이 실행되지 않음

## 문서 반영 원칙

- inference 디렉토리 내 구현/실행 방식이 바뀌면 이 README도 함께 업데이트
