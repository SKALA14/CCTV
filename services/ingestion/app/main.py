# ingestion 서비스 진입점.
# SOURCE_TYPE에 따라 소스를 선택하고 FpsSampler → FramePublisher 순서로 실행한다.

from .config import config
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


def main():
    cls = _SOURCES.get(config.SOURCE_TYPE)
    if cls is None:
        raise ValueError(f"지원하지 않는 SOURCE_TYPE: {config.SOURCE_TYPE}")

    source = cls()
    source.open()

    sampler = FpsSampler(source)
    publisher = FramePublisher()

    for frame in sampler.frames():
        path = publisher.publish(frame)
        print(f"저장: {path}")

    source.close()


if __name__ == "__main__":
    main()
