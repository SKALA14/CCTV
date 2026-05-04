import logging

import cv2
import numpy as np
import time

from .base import FrameSource
from ..config import config

logger = logging.getLogger(__name__)


class RtspSource(FrameSource):

    def __init__(self):
        self._cap = None

    def open(self) -> None:
        for i in range(10):
            self._cap = cv2.VideoCapture(config.SOURCE_PATH)
            if self._cap.isOpened():
                logger.info("RTSP 연결 성공: %s", config.SOURCE_PATH)
                return
            logger.warning("RTSP 연결 실패, 재시도 %d/10", i + 1)
            time.sleep(3)
        raise RuntimeError(f"RTSP 스트림을 열 수 없습니다: {config.SOURCE_PATH}")

    def read_frame(self) -> np.ndarray | None:
        ok, frame = self._cap.read()
        if not ok:
            logger.warning("RTSP 프레임 읽기 실패 — 스트림 종료 또는 연결 끊김")
            return None
        return frame

    def close(self) -> None:
        if self._cap:
            self._cap.release()
            self._cap = None

    def get_fps(self) -> float:
        return self._cap.get(cv2.CAP_PROP_FPS) or 30.0
