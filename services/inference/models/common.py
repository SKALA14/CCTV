def clamp_bbox(box, h: int, w: int) -> list[int]:
    x1, y1, x2, y2 = map(int, box)
    return [
        max(0, min(x1, w - 1)),
        max(0, min(y1, h - 1)),
        max(0, min(x2, w - 1)),
        max(0, min(y2, h - 1)),
    ]
