from pathlib import Path
from datetime import datetime

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
        })

    return {
        "frame": Path(frame_path).name,
        "timestamp": timestamp,
        "anomaly_type": anomaly_type,
        "detections": formatted_detections
    }
