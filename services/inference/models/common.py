# services/inference/models/common.py
"""YOLO 추론 결과 후처리용 공용 헬퍼."""


def clamp_bbox(box, h: int, w: int) -> list[int]:
    """bbox 좌표를 프레임 경계(0..w-1, 0..h-1) 안으로 잘라 정수 리스트로 반환한다."""
    x1, y1, x2, y2 = map(int, box)
    return [
        max(0, min(x1, w - 1)),
        max(0, min(y1, h - 1)),
        max(0, min(x2, w - 1)),
        max(0, min(y2, h - 1)),
    ]
