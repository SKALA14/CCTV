# 샘플링된 프레임을 로컬 볼륨에 JPEG으로 저장한다.
# 카메라별 하위 폴더를 생성하고, 파일명은 timestamp-순번 형식으로 저장한다.

import os
import time

import cv2
import numpy as np
import logging

from .config import config
from .redis_client import get_client

logger = logging.getLogger(__name__)

LOG_INTERVAL = 100  # 100프레임마다 누적 카운트 출력


class FramePublisher:

    def __init__(self):
        self._cam_dir = os.path.join(config.FRAME_STORAGE_PATH, config.CAMERA_ID)
        os.makedirs(self._cam_dir, exist_ok=True)
        self._counter = 1

    def publish(self, frame: np.ndarray) -> str:
        """프레임을 저장하고 Redis 스트림에 경로를 발행한다."""
        ts = time.time()
        filename = f"{ts:.3f}-{self._counter:05d}.jpg"
        path = os.path.join(self._cam_dir, filename)
        cv2.imwrite(path, frame)

        get_client().xadd(config.FRAMES_STREAM, {
            "frame_path": path,
            "camera_id": config.CAMERA_ID,
            "timestamp": str(ts),
        })

        logger.info("프레임 발행 성공: camera=%s count=%d", config.CAMERA_ID, self._counter)

        if self._counter % LOG_INTERVAL == 0:
            logger.info("프레임 발행 누적: camera=%s count=%d", config.CAMERA_ID, self._counter)

        self._counter += 1
        return path
