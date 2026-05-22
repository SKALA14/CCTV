# services/inference/dynamic/buffer.py
"""camera별로 dynamic VLM 후보 프레임을 윈도우 단위로 모은다."""

from __future__ import annotations

import logging
import time
from collections import deque

from config import config

logger = logging.getLogger(__name__)

# (msg_id, frame_path, timestamp)
Candidate = tuple[str, str, str]


class DynamicBuffer:
    """camera별 후보 프레임 버퍼와 윈도우 시작 시각을 관리한다."""

    def __init__(self) -> None:
        self._buffers: dict[str, deque[Candidate]] = {}
        self._window_starts: dict[str, float] = {}
        self._last_call: dict[str, float] = {}

    def append(self, camera_id: str, msg_id: str, frame_path: str, timestamp: str) -> None:
        self._window_starts.setdefault(camera_id, time.time())
        self._buffers.setdefault(camera_id, deque()).append((msg_id, frame_path, timestamp))

    def expired_cameras(self) -> list[str]:
        """GENERAL_WINDOW_SEC 경과한 카메라 id 리스트."""
        now = time.time()
        return [
            cam for cam, ws in self._window_starts.items()
            if now - ws >= config.GENERAL_WINDOW_SEC
        ]

    def pop(self, camera_id: str) -> list[Candidate]:
        """카메라 버퍼를 비우고 후보 리스트 반환."""
        self._window_starts.pop(camera_id, None)
        return list(self._buffers.pop(camera_id, deque()))

    def in_cooldown(self, camera_id: str) -> bool:
        elapsed = time.time() - self._last_call.get(camera_id, 0.0)
        return elapsed < config.GENERAL_MIN_CALL_INTERVAL

    def mark_called(self, camera_id: str) -> None:
        self._last_call[camera_id] = time.time()

    def reset_cooldown(self, camera_id: str) -> None:
        self._last_call[camera_id] = 0.0
