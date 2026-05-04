# ingestion 서비스 진입점.
# SOURCE_TYPE에 따라 소스를 선택하고 FpsSampler → FramePublisher 순서로 실행한다.

import time

from .config import config
from .redis_client import get_client
from .sources.file import FileSource
from .sources.rtsp import RtspSource
from .sources.youtube import YouTubeSource
from .sampler import FpsSampler
from .publisher import FramePublisher

_SOURCES = {
    "file":    FileSource,
    "rtsp":    RtspSource,
    "youtube": YouTubeSource,
}

def wait_for_source():
    client = get_client()
    while True:
        url = client.get(f"camera:{config.CAMERA_ID}:source_url")
        type_ = client.get(f"camera:{config.CAMERA_ID}:source_type")
        if url and type_:
            return url, type_
        time.sleep(2)


def main():
    if not config.SOURCE_PATH or not config.SOURCE_TYPE:
        source_path, source_type = wait_for_source()
    else:
        source_path, source_type = config.SOURCE_PATH, config.SOURCE_TYPE

    cls = _SOURCES.get(source_type)
    if cls is None:
        raise ValueError(f"지원하지 않는 SOURCE_TYPE: {source_type}")

    source = cls()
    source.open(source_path)

    sampler = FpsSampler(source)
    publisher = FramePublisher()

    for frame in sampler.frames():
        path = publisher.publish(frame)
        print(f"저장: {path}")

    source.close()


if __name__ == "__main__":
    main()
