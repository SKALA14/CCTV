# services/inference/dynamic/optical_flow.py
"""연속 프레임 간 Optical Flow를 계산해 움직임 강도를 산출한다."""

from __future__ import annotations

import cv2
import numpy as np


class OpticalFlowDetector:
    """camera_id별로 직전 그레이 프레임을 저장하고 Farneback flow의 크기 합을 반환한다."""

    def __init__(self) -> None:
        self._prev: dict[str, np.ndarray] = {}

    def compute(self, camera_id: str, frame: np.ndarray) -> float:
        """현재 프레임과 직전 프레임 사이의 flow magnitude 합을 반환. 첫 프레임이면 0."""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        prev = self._prev.get(camera_id)
        self._prev[camera_id] = gray
        if prev is None or prev.shape != gray.shape:
            return 0.0

        flow = cv2.calcOpticalFlowFarneback(
            prev, gray, None,
            pyr_scale=0.5, levels=3, winsize=15,
            iterations=3, poly_n=5, poly_sigma=1.2, flags=0,
        )
        magnitude, _ = cv2.cartToPolar(flow[..., 0], flow[..., 1])
        return float(magnitude.sum() / 1000.0)

    def reset(self, camera_id: str) -> None:
        self._prev.pop(camera_id, None)
