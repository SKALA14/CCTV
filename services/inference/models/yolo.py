# YOLO 모델을 로드하고 이미지 파일에 대해 객체 탐지를 수행하는 래퍼를 정의한다.
# 정의: YOLOModel 클래스 — __init__(모델 로드), predict(추론).
# 입력: predict(image_path: str) — JPEG 파일 절대경로.
# 출력: list[dict] — [{"class": "person", "confidence": 0.92, "bbox": [x1,y1,x2,y2]}, ...].

from ultralytics import YOLO
from config import config


class EmergencyYOLO:
    def __init__(self):
        self.model = YOLO(config.EMERGENCY_MODEL_PATH).to(config.DEVICE)
    
    def predict(self, frame_path):
        ...

class GeneralYOLO:
    def __init__(self):
        self.model = YOLO(config.GENERAL_MODEL_PATH).to(config.DEVICE)
    
    def predict(self, frame_path):
        ...