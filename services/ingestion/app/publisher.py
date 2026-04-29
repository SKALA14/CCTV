# 샘플링된 프레임을 로컬 볼륨에 JPEG으로 저장한다.
# 카메라별 하위 폴더를 생성하고, 파일명은 timestamp-순번 형식으로 저장한다.

import os
import time

import cv2
import numpy as np
import logging
import redis

from .config import config

logger = logging.getLogger(__name__)

_redis_client = None


def _get_client() -> redis.Redis:
    global _redis_client
    if _redis_client is not None:
        return _redis_client

    for attempt in range(1, 6):
        try:
            client = redis.from_url(config.REDIS_URL, decode_responses=True)
            client.ping()
            _redis_client = client
            return _redis_client
        except redis.exceptions.ConnectionError:
            logger.warning("Redis 연결 실패 (%d/5), 3초 후 재시도", attempt)
            time.sleep(3)

    raise RuntimeError("Redis에 연결할 수 없습니다")


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
        self._counter += 1

        _get_client().xadd(config.FRAMES_STREAM, {
            "frame_path": path,
            "camera_id": config.CAMERA_ID,
            "timestamp": str(ts),
        })

        return path
