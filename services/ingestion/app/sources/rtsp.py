# RTSP 스트림 인풋에 대응하는 구현체
# 연결 실패 시 3초 간격으로 최대 10회 재시도한다.

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

    def open(self, path: str) -> None:
        for i in range(10):
            logger.info("RTSP 연결 시도 중: url=%s (%d/10)", path, i + 1)
            self._cap = cv2.VideoCapture(path)
            if self._cap.isOpened():
                logger.info("RTSP 연결 성공: %s", path)
                return
            logger.warning("RTSP 연결 실패 (url=%s), 3초 후 재시도 %d/10", path, i + 1)
            time.sleep(3)
        logger.error("RTSP 연결 최종 실패 (url=%s), 10회 모두 실패", path)
        raise RuntimeError(f"RTSP 스트림을 열 수 없습니다: {path}")

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
