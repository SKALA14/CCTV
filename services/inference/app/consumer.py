# 프레임 소비자 모듈.
# 로컬 영상 저장소(폴더 내 이미지)에서 프레임을 읽어 inference 파이프라인에 전달한다.
# 0.5초 간격마다 프레임을 추출해 분석을 진행한다.

from pathlib import Path
import json
import re
from datetime import datetime
import cv2
from ultralytics import YOLO
import psutil

# =========================
# 설정값
# =========================
MODEL_PATH = "models/best.pt"
FRAMES_DIR = Path("../../frames/video0") # 상위 폴더 경로 반영
FPS = 30.0 # 이미지 시퀀스이므로 가상의 FPS 설정

# 프레임 스킵 설정 (0.5초 간격)
SAMPLE_INTERVAL_SEC = 0.5
FRAME_STEP = int(FPS * SAMPLE_INTERVAL_SEC) # 30 * 0.5 = 15 프레임

CONF = 0.15
IOU = 0.45
IMGSZ = 960

# 같은 클래스가 이 시간 안에 계속 보이면 같은 이벤트로 간주
EVENT_END_GAP_SEC = 2.0

# 저장할 클래스
TARGET_CLASSES = {"fire", "smoke"}

OUTPUT_DIR = Path("output")
FULL_FRAME_DIR = OUTPUT_DIR / "full_frames"
EVENT_DIR = OUTPUT_DIR / "events"


def setup_dirs():
    FULL_FRAME_DIR.mkdir(parents=True, exist_ok=True)
    EVENT_DIR.mkdir(parents=True, exist_ok=True)


def load_model(model_path: str) -> YOLO:
    model = YOLO(model_path)
    print("모델 클래스:", model.names)
    return model


def clamp_bbox(box, frame_shape):
    h, w = frame_shape[:2]

    x1, y1, x2, y2 = map(int, box)
    x1 = max(0, min(x1, w - 1))
    y1 = max(0, min(y1, h - 1))
    x2 = max(0, min(x2, w - 1))
    y2 = max(0, min(y2, h - 1))

    return [x1, y1, x2, y2]


def get_class_name(model, cls_id):
    if isinstance(model.names, dict):
        return model.names.get(cls_id, str(cls_id))
    return model.names[cls_id]


def should_start_new_event(class_name, timestamp_sec, active_events):
    """
    같은 클래스가 계속 탐지되면 같은 이벤트.
    마지막으로 본 시점에서 EVENT_END_GAP_SEC 이상 끊겼다가 다시 나오면 새 이벤트.
    """
    if class_name not in active_events:
        active_events[class_name] = {"last_seen_time": timestamp_sec}
        return True

    last_seen_time = active_events[class_name]["last_seen_time"]
    time_gap = timestamp_sec - last_seen_time

    # 현재 시점으로 갱신
    active_events[class_name]["last_seen_time"] = timestamp_sec

    if time_gap > EVENT_END_GAP_SEC:
        return True

    return False


def build_vlm_payload(frame_filename, class_name, confidence, bbox):
    current_time = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    payload = {
        "frame": frame_filename,
        "timestamp": current_time,
        "anomaly_type": f"{class_name}_anomaly",
        "detections": [
            {
                "track_id": None,
                "class": class_name,
                "conf": round(float(confidence), 4),
                "bbox": bbox,
                "keypoints": None
            }
        ]
    }
    return payload


def save_json_with_inline_bbox(data, json_path):
    json_text = json.dumps(data, ensure_ascii=False, indent=2)

    json_text = re.sub(
        r'"bbox":\s*\[\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*\]',
        r'"bbox": [\1, \2, \3, \4]',
        json_text
    )

    with open(json_path, "w", encoding="utf-8") as f:
        f.write(json_text)


def save_detection_event(frame, box, class_name, confidence, event_id):
    x1, y1, x2, y2 = clamp_bbox(box, frame.shape)

    if x2 <= x1 or y2 <= y1:
        return None

    frame_filename = f"{event_id}.jpg"
    json_filename = f"{event_id}.json"

    full_frame_path = FULL_FRAME_DIR / frame_filename
    json_path = EVENT_DIR / json_filename

    image_saved = cv2.imwrite(str(full_frame_path), frame)
    if not image_saved:
        print(f"⚠️ full frame 저장 실패: {full_frame_path}")
        return None

    vlm_payload = build_vlm_payload(
        frame_filename=frame_filename,
        class_name=class_name,
        confidence=confidence,
        bbox=[x1, y1, x2, y2]
    )

    save_json_with_inline_bbox(vlm_payload, json_path)

    return {
        "json_path": str(json_path),
        "frame_path": str(full_frame_path),
        "payload": vlm_payload
    }


def run_detection(model: YOLO, frames_dir: Path):
    if not frames_dir.exists():
        print(f"❌ 폴더를 찾을 수 없습니다: {frames_dir}")
        return

    # 폴더 내의 jpg 이미지 목록을 정렬하여 가져옴
    image_paths = sorted(frames_dir.glob("*.jpg"))
    total_frames = len(image_paths)
    
    if total_frames == 0:
        print(f"❌ 폴더에 이미지 파일이 없습니다: {frames_dir}")
        return

    print(f"✅ 총 {total_frames}개의 프레임을 찾았습니다. 분석을 시작합니다.")

    # 클래스별 마지막 탐지 시점
    active_events = {}

    # 클래스별 이벤트 번호
    event_counter_by_class = {}
    
    # 실제로 분석한 프레임 수를 세기 위한 변수
    processed_count = 0 

    for frame_idx, img_path in enumerate(image_paths):
        # 🌟 핵심 로직: 설정한 FRAME_STEP(15) 배수에 해당하는 프레임만 분석하고 나머지는 건너뜀
        if frame_idx % FRAME_STEP != 0:
            continue
            
        processed_count += 1
        
        frame = cv2.imread(str(img_path))
        if frame is None:
            print(f"⚠️ 이미지를 읽지 못했습니다: {img_path}")
            continue

        results = model(
            frame,
            conf=CONF,
            iou=IOU,
            imgsz=IMGSZ,
            verbose=False
        )

        result = results[0]

        # 타임스탬프는 원본 프레임 인덱스 기준으로 계산 (정확한 시간 기록을 위해)
        timestamp_sec = frame_idx / FPS

        # 한 프레임 안에서는 클래스별 confidence 가장 높은 detection 1개만 사용
        best_detection_by_class = {}

        if result.boxes is not None and len(result.boxes) > 0:
            for box in result.boxes:
                cls_id = int(box.cls[0].item())
                confidence = float(box.conf[0].item())
                xyxy = box.xyxy[0].tolist()

                class_name = get_class_name(model, cls_id)

                if class_name not in TARGET_CLASSES:
                    continue

                clamped_bbox = clamp_bbox(xyxy, frame.shape)

                if clamped_bbox[2] <= clamped_bbox[0] or clamped_bbox[3] <= clamped_bbox[1]:
                    continue

                prev = best_detection_by_class.get(class_name)
                if prev is None or confidence > prev["confidence"]:
                    best_detection_by_class[class_name] = {
                        "confidence": confidence,
                        "bbox": clamped_bbox
                    }

        for class_name, det in best_detection_by_class.items():
            is_new_event = should_start_new_event(
                class_name=class_name,
                timestamp_sec=timestamp_sec,
                active_events=active_events
            )

            if not is_new_event:
                continue

            event_counter_by_class[class_name] = event_counter_by_class.get(class_name, 0) + 1
            event_number = event_counter_by_class[class_name]

            now_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            event_id = f"{class_name}_anomaly_{now_str}_{event_number:04d}"

            saved_event = save_detection_event(
                frame=frame,
                box=det["bbox"],
                class_name=class_name,
                confidence=det["confidence"],
                event_id=event_id
            )

            if saved_event is not None:
                print(
                    f"[SAVE] event_id={event_id} | "
                    f"class={class_name} | "
                    f"conf={det['confidence']:.3f} | "
                    f"bbox={det['bbox']} | "
                    f"json={saved_event['json_path']}"
                )

        # 분석을 10번 수행할 때마다 모니터링 로그 출력
        if processed_count % 10 == 0:
            cpu_usage = psutil.cpu_percent(interval=None)
            ram_usage = psutil.virtual_memory().percent
            print(f"📊 [모니터링] CPU: {cpu_usage:>4.1f}% | RAM: {ram_usage:>4.1f}% | 진행률: {frame_idx + 1}/{total_frames}")

    print("✅ 분석이 모두 완료되었습니다.")


def main():
    print("🔥 YOLOv8 로컬 프레임 영상 테스트를 시작합니다...")
    setup_dirs()

    model = load_model(MODEL_PATH)
    run_detection(model, FRAMES_DIR)


if __name__ == "__main__":
    main()