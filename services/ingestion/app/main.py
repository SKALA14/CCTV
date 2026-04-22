# ingestion 서비스 진입점.
# FileSource → FpsSampler → FramePublisher 순서로 실행한다.

from .sources.file import FileSource
from .sampler import FpsSampler
from .publisher import FramePublisher


def main():
    source = FileSource()
    source.open()

    sampler = FpsSampler(source)
    publisher = FramePublisher()

    for frame in sampler.frames():
        path = publisher.publish(frame)
        print(f"저장: {path}")

    source.close()


if __name__ == "__main__":
    main()
