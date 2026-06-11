# services/inference/dynamic/optical_flow.py
"""연속 프레임으로부터 Dual-EMA trigger용 시각 feature를 추출한다."""

from __future__ import annotations

import cv2
import numpy as np


class FrameFeatureExtractor:
    """camera_id별 상태를 유지하며 매 프레임의 시각 feature를 추출한다.

    반환 dict는 RealtimeTriggerSelector.process()에 그대로 넣을 수 있다.
    """

    def __init__(self) -> None:
        self._subtractors: dict[str, cv2.BackgroundSubtractorMOG2] = {}
        self._prev_gray: dict[str, np.ndarray] = {}
        self._prev_fg_ratio: dict[str, float] = {}
        self._prev_mask: dict[str, np.ndarray] = {}

    def extract(self, camera_id: str, frame: np.ndarray, timestamp_sec: float) -> dict:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        total_pixels = float(gray.size)

        subtractor = self._subtractors.setdefault(
            camera_id,
            cv2.createBackgroundSubtractorMOG2(history=200, varThreshold=16, detectShadows=False),
        )
        fg_mask = subtractor.apply(frame)
        fg_pixels = float(np.count_nonzero(fg_mask))
        fg_ratio = fg_pixels / total_pixels if total_pixels > 0 else 0.0

        prev_fg_ratio = self._prev_fg_ratio.get(camera_id, fg_ratio)
        fg_delta = abs(fg_ratio - prev_fg_ratio)
        self._prev_fg_ratio[camera_id] = fg_ratio

        n_labels, _, stats, _ = cv2.connectedComponentsWithStats(fg_mask, connectivity=8)
        component_count = max(0, n_labels - 1)
        if component_count > 0:
            largest_area = float(stats[1:, cv2.CC_STAT_AREA].max())
        else:
            largest_area = 0.0
        largest_component_ratio = largest_area / total_pixels if total_pixels > 0 else 0.0
        largest_component_share = largest_area / fg_pixels if fg_pixels > 0 else 0.0

        prev_gray = self._prev_gray.get(camera_id)
        self._prev_gray[camera_id] = gray

        prev_mask = self._prev_mask.get(camera_id)
        self._prev_mask[camera_id] = fg_mask.copy()

        if prev_gray is None or prev_gray.shape != gray.shape:
            appearance_change = 0.0
            flow_p90 = 0.0
        else:
            diff = cv2.absdiff(prev_gray, gray)
            appearance_change = float(diff.mean()) / 255.0

            flow = cv2.calcOpticalFlowFarneback(
                prev_gray, gray, None,
                pyr_scale=0.5, levels=3, winsize=15,
                iterations=3, poly_n=5, poly_sigma=1.2, flags=0,
            )
            mean_u = float(flow[..., 0].mean())
            mean_v = float(flow[..., 1].mean())
            residual_mag, _ = cv2.cartToPolar(flow[..., 0] - mean_u, flow[..., 1] - mean_v)
            fg_region = fg_mask > 0
            flow_p90 = float(np.percentile(residual_mag[fg_region], 90)) if fg_region.any() else 0.0

        if prev_mask is not None and prev_mask.shape == fg_mask.shape:
            union = int(np.count_nonzero(fg_mask | prev_mask))
            intersection = int(np.count_nonzero(fg_mask & prev_mask))
            mask_novelty = 1.0 - intersection / union if union > 0 else 0.0
        else:
            mask_novelty = 0.0

        return {
            "timestamp_sec": timestamp_sec,
            "appearance_change": appearance_change,
            "foreground_residual_flow_p90": flow_p90,
            "foreground_delta": fg_delta,
            "foreground_ratio": fg_ratio,
            "component_count": float(component_count),
            "largest_component_ratio": largest_component_ratio,
            "largest_component_share": largest_component_share,
            "mask_novelty": mask_novelty,
        }

    def reset(self, camera_id: str) -> None:
        for store in (self._subtractors, self._prev_gray, self._prev_fg_ratio, self._prev_mask):
            store.pop(camera_id, None)
