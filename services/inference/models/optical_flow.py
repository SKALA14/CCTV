'''
카메라별 optical flow spike timing을 계산한다.

입력
- camera_id: CCTV 채널 또는 화면을 구분하는 ID.
- frame: cv2.imread()로 읽은 BGR 프레임.

내부 상태
- prev_gray_by_camera: camera_id별 직전 grayscale resized frame 1장만 저장한다.
- prev_seen_at: camera_id별 마지막 입력 시각을 저장해 오래된 상태를 정리한다.

출력
- OpticalFlowResult
- is_spike: 현재 프레임이 직전 프레임 대비 움직임 기준값을 넘었는지 여부.
- score: optical flow magnitude의 percentile score.

주의
- 원본 프레임 전체를 저장하지 않고 resized grayscale 1장만 보관해 메모리 사용을 제한한다.
'''

from dataclasses import dataclass
import time

import cv2
import numpy as np


@dataclass(frozen=True)
class OpticalFlowResult:
    is_spike: bool
    score: float


class OpticalFlowGate:
    def __init__(
        self,
        resize_width: int,
        threshold: float,
        percentile: float,
        state_ttl_sec: float,
    ):
        self.resize_width = resize_width
        self.threshold = threshold
        self.percentile = max(0.0, min(100.0, percentile))
        self.state_ttl_sec = state_ttl_sec
        self.prev_gray_by_camera: dict[str, np.ndarray] = {}
        self.prev_seen_at: dict[str, float] = {}
        self._last_cleanup_at = 0.0

    def evaluate(self, camera_id: str, frame: np.ndarray) -> OpticalFlowResult:
        now = time.monotonic()
        self._cleanup_expired(now)

        gray = self._to_resized_gray(frame)
        prev_gray = self.prev_gray_by_camera.get(camera_id)

        # 현재 프레임은 판정 결과와 무관하게 다음 비교 기준으로 갱신한다.
        self.prev_gray_by_camera[camera_id] = gray
        self.prev_seen_at[camera_id] = now

        if prev_gray is None:
            return OpticalFlowResult(False, 0.0)

        if prev_gray.shape != gray.shape:
            return OpticalFlowResult(False, 0.0)

        flow = cv2.calcOpticalFlowFarneback(
            prev_gray,
            gray,
            None,
            pyr_scale=0.5,
            levels=3,
            winsize=15,
            iterations=3,
            poly_n=5,
            poly_sigma=1.2,
            flags=0,
        )
        magnitude, _ = cv2.cartToPolar(flow[..., 0], flow[..., 1])
        score = float(np.percentile(magnitude, self.percentile))

        if score >= self.threshold:
            return OpticalFlowResult(True, round(score, 4))
        return OpticalFlowResult(False, round(score, 4))

    def _to_resized_gray(self, frame: np.ndarray) -> np.ndarray:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        if self.resize_width <= 0 or gray.shape[1] <= self.resize_width:
            return gray

        scale = self.resize_width / gray.shape[1]
        resize_height = max(1, int(gray.shape[0] * scale))
        return cv2.resize(gray, (self.resize_width, resize_height), interpolation=cv2.INTER_AREA)

    def _cleanup_expired(self, now: float) -> None:
        # 매 프레임마다 전체 dict를 순회하지 않도록 정리 주기를 제한한다.
        if self.state_ttl_sec <= 0 or now - self._last_cleanup_at < 30.0:
            return

        expired = [
            camera_id
            for camera_id, seen_at in self.prev_seen_at.items()
            if now - seen_at > self.state_ttl_sec
        ]
        for camera_id in expired:
            self.prev_gray_by_camera.pop(camera_id, None)
            self.prev_seen_at.pop(camera_id, None)

        self._last_cleanup_at = now
