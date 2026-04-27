```
main.py
  │
  ├── init_consumer_groups()       # redis_client.py
  │
  ├── Process(emergency_pipeline)  # pipelines/emergency.py
<<<<<<< HEAD
  │     └── models/yolo_e.py         # YOLO 추론
  │
  ├── Process(general_pipeline)    # pipelines/general.py
  │     ├── models/yolo_g.py
=======
  │     └── models/yolo.py         # YOLO 추론
  │
  ├── Process(general_pipeline)    # pipelines/general.py
>>>>>>> c97d5194f1de9a997e76d77cbbb2a07a9e63263d
  │     ├── models/vlm.py          # GPT-4o 호출
  │     └── prompts/               # VLM 프롬프트 템플릿
  │
  └── Process(cleaner_process)     # cleaner.py
  ```