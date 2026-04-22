# 샘플링된 프레임을 로컬 볼륨에 JPEG으로 저장한다.
# 카메라별 하위 폴더를 생성하고, 파일명은 timestamp-순번 형식으로 저장한다.

import os
import time

import cv2
import numpy as np

from .config import config


class FramePublisher:

    def __init__(self):
        self._cam_dir = os.path.join(config.FRAME_STORAGE_PATH, config.CAMERA_ID)
        os.makedirs(self._cam_dir, exist_ok=True)
        self._counter = 1

    def publish(self, frame: np.ndarray) -> str:
        """프레임을 저장하고 저장된 경로를 반환한다."""
        filename = f"{time.time():.3f}-{self._counter:05d}.jpg"
        path = os.path.join(self._cam_dir, filename)
        cv2.imwrite(path, frame)
        self._counter += 1
        return path
