# ingestion 서비스 진입점.
# SOURCE_TYPE에 따라 소스를 선택하고 FpsSampler → FramePublisher 순서로 실행한다.

import time
import logging

from .config import config
from .redis_client import get_client
from .sources.file import FileSource
from .sources.rtsp import RtspSource
from .sources.youtube import YouTubeSource
from .sampler import FpsSampler
from .publisher import FramePublisher

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(name)s [%(levelname)s] %(message)s",
)

_SOURCES = {
    "file":    FileSource,
    "rtsp":    RtspSource,
    "youtube": YouTubeSource,
}

def wait_for_source():
    client = get_client()
    logger.info("소스 대기 중 (camera_id=%s)", config.CAMERA_ID)
    while True:
        url = client.get(f"camera:{config.CAMERA_ID}:source_url")
        type_ = client.get(f"camera:{config.CAMERA_ID}:source_type")
        if url and type_:
            logger.info("소스 수신 (type=%s, url=%s)", type_, url)
            return url, type_
        time.sleep(2)


def main():
    client = get_client()
    if config.SOURCE_PATH and config.SOURCE_TYPE:
        source_path, source_type = config.SOURCE_PATH, config.SOURCE_TYPE
    else:
        source_path, source_type = wait_for_source()

    while True:
        cls = _SOURCES.get(source_type)
        if cls is None:
            raise ValueError(f"지원하지 않는 SOURCE_TYPE: {source_type}")

        source = cls()
        source.open(source_path)

        realtime = source_type in ("youtube", "file")
        sampler = FpsSampler(source, realtime=realtime)
        publisher = FramePublisher()

        check_interval = max(1, int(config.SAMPLE_FPS) * 5)  # 5초마다 확인
        for i, frame in enumerate(sampler.frames()):
            if i % check_interval == 0:
                if not client.exists(f"camera:{config.CAMERA_ID}:source_url"):
                    logger.info("소스 키 삭제됨, ingestion 종료 (camera_id=%s)", config.CAMERA_ID)
                    break
            publisher.publish(frame)

        source.close()

        if source_type == "file":
            client.delete(f"camera:{config.CAMERA_ID}:source_url")
            client.delete(f"camera:{config.CAMERA_ID}:source_type")
            logger.info("파일 재생 완료, 다음 소스 대기 (camera_id=%s)", config.CAMERA_ID)

        source_path, source_type = wait_for_source()


if __name__ == "__main__":
    main()
