# YOLO 모델을 로드하고 이미지 파일에 대해 객체 탐지를 수행하는 래퍼를 정의한다.
# 정의: YOLOModel 클래스 — __init__(모델 로드), predict(추론).
# 입력: predict(image_path: str) — JPEG 파일 절대경로.
# 출력: list[dict] — [{"class": "person", "confidence": 0.92, "bbox": [x1,y1,x2,y2]}, ...].

import cv2
import json
from pathlib import Path
from datetime import datetime
from ultralytics import YOLO


def clamp_bbox(box, h, w):
    """박스 좌표가 이미지 밖을 벗어나지 않도록 보정"""
    x1, y1, x2, y2 = map(int, box)
    return [
        max(0, min(x1, w - 1)),
        max(0, min(y1, h - 1)),
        max(0, min(x2, w - 1)),
        max(0, min(y2, h - 1))
    ]


def build_output_payload(frame_path: str, anomaly_type: str, detections: list[dict]) -> dict:
    """
    출력 형식을 VLM / downstream 모듈에 넘기기 좋은 JSON 구조로 변환
    """
    timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    formatted_detections = []

    for idx, det in enumerate(detections, start=1):
        formatted_detections.append({
            "track_id": det.get("track_id", idx),
            "class": det["class"],
            "conf": det["confidence"],
            "bbox": det["bbox"],
            "keypoints": det.get("keypoints")
        })

    return {
        "frame": Path(frame_path).name,
        "timestamp": timestamp,
        "anomaly_type": anomaly_type,
        "detections": formatted_detections
    }


# ======================================================
# 1. Emergency Pipeline Class
# 불꽃, 연기, 화재 + 쓰러짐/추락 후보
# ======================================================
class EmergencyYOLO:
    def __init__(self):
        self.fire_model = YOLO("models/fire.pt")
        self.pose_model = YOLO("models/yolo26m-pose.pt")

        self.fire_classes = {"fire", "smoke"}

        print("✅ EmergencyYOLO 로드 완료 (fire.pt, yolo26m-pose.pt)")

    def predict(self, image_path: str) -> list[dict]:
        frame = cv2.imread(image_path)

        if frame is None:
            return []

        h, w = frame.shape[:2]
        detections = []

        # [1] 화재/연기 탐지
        fire_results = self.fire_model(
            frame,
            conf=0.15,
            imgsz=960,
            verbose=False
        )

        if fire_results[0].boxes is not None:
            for box in fire_results[0].boxes:
                cls_id = int(box.cls[0].item())
                class_name = self.fire_model.names[cls_id]

                if class_name in self.fire_classes:
                    detections.append({
                        "track_id": None,
                        "class": class_name,
                        "confidence": round(float(box.conf[0].item()), 4),
                        "bbox": clamp_bbox(box.xyxy[0].tolist(), h, w),
                        "keypoints": None
                    })

        # [2] 포즈 탐지
        pose_results = self.pose_model(
            frame,
            conf=0.5,
            imgsz=960,
            verbose=False
        )

        if pose_results[0].boxes is not None:
            for idx, box in enumerate(pose_results[0].boxes):
                cls_id = int(box.cls[0].item())
                class_name = self.pose_model.names[cls_id]

                if class_name == "person":
                    keypoints = None

                    if pose_results[0].keypoints is not None:
                        keypoints = pose_results[0].keypoints.data[idx].tolist()

                    detections.append({
                        "track_id": idx + 1,
                        "class": "person",
                        "confidence": round(float(box.conf[0].item()), 4),
                        "bbox": clamp_bbox(box.xyxy[0].tolist(), h, w),
                        "keypoints": keypoints
                    })

        return detections


# ===================================================
# 2. General Pipeline Class
# 침수 + 폭행, 침입 + 규정 준수 후보
# ===================================================
class GeneralYOLO:
    def __init__(self):
        self.model = YOLO("models/yolo26m.pt")

        # 우선 person만 탐지
        self.target_classes = {"person"}

        print("✅ GeneralYOLO 로드 완료 (yolo26m.pt)")

    def predict(self, image_path: str) -> list[dict]:
        frame = cv2.imread(image_path)

        if frame is None:
            return []

        h, w = frame.shape[:2]
        detections = []

        results = self.model(
            frame,
            conf=0.25,
            imgsz=640,
            verbose=False
        )

        if results[0].boxes is not None:
            for idx, box in enumerate(results[0].boxes):
                cls_id = int(box.cls[0].item())
                class_name = self.model.names[cls_id]

                if class_name in self.target_classes:
                    detections.append({
                        "track_id": idx + 1,
                        "class": class_name,
                        "confidence": round(float(box.conf[0].item()), 4),
                        "bbox": clamp_bbox(box.xyxy[0].tolist(), h, w),
                        "keypoints": None
                    })

        return detections


# ===================================================
# 테스트 코드
# ===================================================
if __name__ == "__main__":
    test_dir = Path("../../frames/video0")
    test_images = sorted(test_dir.glob("*.jpg"))

    if not test_images:
        print(f"❌ 폴더에 테스트할 이미지가 없습니다: {test_dir}")

    else:
        print(f"✅ 총 {len(test_images)}장의 이미지를 찾았습니다. 테스트를 시작합니다.")

        emergency_pipeline = EmergencyYOLO()
        general_pipeline = GeneralYOLO()

        for img_path in test_images[:5]:
            print(f"\n프레임 분석 중: {img_path}")

            # =========================
            # Emergency YOLO 실행
            # =========================
            emergency_results = emergency_pipeline.predict(str(img_path))

            print("\n- [Emergency YOLO]")

            if not emergency_results:
                print("  탐지 결과 없음")

            else:
                emergency_payload = build_output_payload(
                    frame_path=str(img_path),
                    anomaly_type="emergency_anomaly",
                    detections=emergency_results
                )

                print(json.dumps(emergency_payload, ensure_ascii=False, indent=2))

            # =========================
            # General YOLO 실행
            # =========================
            general_results = general_pipeline.predict(str(img_path))

            print("\n- [General YOLO]")

            if not general_results:
                print("  탐지 결과 없음")

            else:
                general_payload = build_output_payload(
                    frame_path=str(img_path),
                    anomaly_type="general_yolo_candidate",
                    detections=general_results
                )

                print(json.dumps(general_payload, ensure_ascii=False, indent=2))
