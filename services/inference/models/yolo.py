# YOLO 모델을 로드하고 이미지 파일에 대해 객체 탐지를 수행하는 래퍼를 정의한다.
# 정의: YOLOModel 클래스 — __init__(모델 로드), predict(추론).
# 입력: predict(image_path: str) — JPEG 파일 절대경로.
# 출력: list[dict] — [{"class": "person", "confidence": 0.92, "bbox": [x1,y1,x2,y2]}, ...].

import math
import cv2
import json
from pathlib import Path
from datetime import datetime
from ultralytics import YOLO


def clamp_bbox(box, h: int, w: int) -> list[int]:
    x1, y1, x2, y2 = map(int, box)
    return [
        max(0, min(x1, w - 1)),
        max(0, min(y1, h - 1)),
        max(0, min(x2, w - 1)),
        max(0, min(y2, h - 1)),
    ]


# ======================================================
# 1-a. 화재/연기 탐지
# ======================================================
class FireYOLO:
    FIRE_CLASSES = {"fire", "smoke"}

    def __init__(self):
        self.model = YOLO("models/fire.pt")

    def predict(self, frame, h: int, w: int) -> list[dict]:
        results = self.model(frame, conf=0.15, imgsz=960, verbose=False)
        detections = []

        if results[0].boxes is None:
            return detections

        for box in results[0].boxes:
            cls_id = int(box.cls[0].item())
            class_name = self.model.names[cls_id]
            if class_name in self.FIRE_CLASSES:
                detections.append({
                    "track_id": None,
                    "anomaly_type": class_name,
                    "confidence": round(float(box.conf[0].item()), 4),
                })

        return detections


# ======================================================
# 1-b. 포즈(쓰러짐/추락) 탐지
# ======================================================
class PoseYOLO:
    # COCO keypoint 인덱스
    _NOSE             = 0
    _L_SHOULDER, _R_SHOULDER = 5, 6
    _L_HIP,      _R_HIP      = 11, 12
    _CONF_THRESH      = 0.3

    def __init__(self):
        self.model = YOLO("models/yolo26m-pose.pt")

    @staticmethod
    def _is_fallen(pts, cf, bbox) -> bool:
        """
        점수 기준 (2점 이상 → 낙상):
          +2  토르소 각도: 어깨-엉덩이 벡터가 수직에서 55° 이상 기울어진 경우
          +2  코 위치: nose y > 엉덩이 중점 y (머리가 엉덩이보다 아래)
          +1  bbox 비율: width / height > 1.3
        """
        L_SH, R_SH   = PoseYOLO._L_SHOULDER, PoseYOLO._R_SHOULDER
        L_HIP, R_HIP = PoseYOLO._L_HIP,      PoseYOLO._R_HIP
        NOSE         = PoseYOLO._NOSE
        T            = PoseYOLO._CONF_THRESH

        if not (cf[L_SH] > T and cf[R_SH] > T and cf[L_HIP] > T and cf[R_HIP] > T):
            return False

        sh_mid  = (pts[L_SH]  + pts[R_SH])  / 2
        hip_mid = (pts[L_HIP] + pts[R_HIP]) / 2

        dx = float(hip_mid[0] - sh_mid[0])
        dy = float(hip_mid[1] - sh_mid[1])
        torso_len = math.hypot(dx, dy)
        if torso_len < 1e-6:
            return False

        angle = math.degrees(math.acos(min(abs(dy) / torso_len, 1.0)))

        score = 0
        if angle > 55:
            score += 2
        if cf[NOSE] > T and float(pts[NOSE][1]) > float(hip_mid[1]):
            score += 2

        x1, y1, x2, y2 = bbox
        bw, bh = float(x2 - x1), float(y2 - y1)
        if bh > 0 and bw / bh > 1.3:
            score += 1

        return score >= 2

    def predict(self, frame, h: int, w: int) -> list[dict]:
        results = self.model.track(frame, conf=0.5, imgsz=960, persist=True, verbose=False)
        detections = []

        if results[0].boxes is None or results[0].keypoints is None:
            return detections

        kpts  = results[0].keypoints.xy
        confs = results[0].keypoints.conf
        boxes = results[0].boxes

        for idx, box in enumerate(boxes):
            cls_id = int(box.cls[0].item())
            if self.model.names[cls_id] != "person":
                continue

            track_id = None
            if boxes.id is not None:
                track_id = int(boxes.id[idx].item())

            fallen = self._is_fallen(kpts[idx], confs[idx], box.xyxy[0])

            detections.append({
                "track_id":    track_id,
                "anomaly_type": "fallen" if fallen else "person",
                "confidence":  round(float(box.conf[0].item()), 4),
                "bbox":        clamp_bbox(box.xyxy[0].tolist(), h, w),
                "keypoints":   results[0].keypoints.data[idx].tolist(),
            })

        return detections


# ======================================================
# 1. Emergency Pipeline — FireYOLO + PoseYOLO 조합
# ======================================================
class EmergencyYOLO:
    def __init__(self):
        self.fire = FireYOLO()
        self.pose = PoseYOLO()

    def predict(self, image_path: str) -> list[dict]:
        frame = cv2.imread(image_path)
        if frame is None:
            return []

        h, w = frame.shape[:2]
        return self.fire.predict(frame, h, w) + self.pose.predict(frame, h, w)


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
