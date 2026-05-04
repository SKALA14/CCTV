# 파일(로컬 .mp4) 인풋에 대응하는 구현체

import cv2
import numpy as np

from .base import FrameSource
from ..config import config


class FileSource(FrameSource):

    def __init__(self):
        self._cap = None

    def open(self, path: str) -> None:
        self._cap = cv2.VideoCapture(path)
        if not self._cap.isOpened():
            raise RuntimeError(f"영상 파일을 열 수 없습니다: {path}")

    def read_frame(self) -> np.ndarray | None:
        ok, frame = self._cap.read()
        return frame if ok else None

    def close(self) -> None:
        if self._cap:
            self._cap.release()
            self._cap = None

    def get_fps(self) -> float:
        return self._cap.get(cv2.CAP_PROP_FPS) or 30.0
