# FPS 기반 프레임 샘플러.
# FrameSource에서 읽은 프레임 중 SAMPLE_FPS 간격에 해당하는 프레임만 yield한다.

import time

from .sources.base import FrameSource
from .config import config


class FpsSampler:

    def __init__(self, source: FrameSource):
        self.source = source

    def frames(self):
        """샘플링된 프레임을 실시간 간격으로 yield. 소스가 끝나면 종료."""
        source_fps = self.source.get_fps()
        interval   = max(1, round(source_fps / config.SAMPLE_FPS))
        sleep_sec  = 1.0 / config.SAMPLE_FPS

        frame_idx = 0
        while True:
            frame = self.source.read_frame()
            if frame is None:
                return

            if frame_idx % interval == 0:
                yield frame
                if config.REALTIME_SIMULATION:
                    time.sleep(sleep_sec)

            frame_idx += 1
