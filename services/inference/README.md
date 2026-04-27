```
main.py
  │
  ├── init_consumer_groups()       # redis_client.py
  │
  ├── Process(emergency_pipeline)  # pipelines/emergency.py
  │     └── models/yolo.py/EmergencyYOLO         # YOLO 추론
  │
  ├── Process(general_pipeline)    # pipelines/general.py
  │     ├── models/yolo.py/GeneralYOLO
  │     ├── models/vlm.py          # GPT-4o 호출
  │     └── prompts/               # VLM 프롬프트 템플릿
  │
  └── Process(cleaner_process)     # cleaner.py
  ```