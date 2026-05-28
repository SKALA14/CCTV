'''
탐지 결과의 bbox를 프레임 이미지에 그려 저장하는 보조 기능을 담당한다.

입력
- frame_path: bbox를 그릴 원본 JPEG 경로.
- detections: ModelResult.detections를 합친 목록.
- 각 detection은 bbox: [x1, y1, x2, y2], anomaly_type, track_id(optional)를 가질 수 있다.

출력/부수효과
- bbox가 있는 detection만 OpenCV로 그린 뒤 같은 frame_path에 덮어쓴다.
- bbox가 없는 fire/general 후보 결과는 annotation 대상에서 제외된다.
'''

import cv2

from config import config


def annotate_and_save(frame_path: str, detections: list[dict]) -> None:
    frame = cv2.imread(frame_path)
    if frame is None:
        return

    for det in detections:
        bbox = det.get("bbox")
        track_id = det.get("track_id")
        atype = det.get("anomaly_type", "person")

        if not bbox:
            continue

        x1, y1, x2, y2 = map(int, bbox)
        color = tuple(config.ANNOTATION_COLORS.get(atype, (255, 255, 255)))
        label = f"id:{track_id} {atype}" if track_id is not None else atype

        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
        cv2.putText(frame, label, (x1, y1 - 6),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2)

    cv2.imwrite(frame_path, frame)
