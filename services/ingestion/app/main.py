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
    """Redis에서 이 컨테이너의 카메라 슬롯에 해당하는 소스 정보를 기다린다.

    멀티테넌시 포맷: camera:{site_id}:{CAMERA_ID}:source_url
    site_id를 함께 반환해 frames 스트림에 포함시킨다.
    """
    client = get_client()
    logger.info("소스 대기 중 (camera_id=%s)", config.CAMERA_ID)
    while True:
        # 새 포맷: camera:{site_id}:{CAMERA_ID}:source_url
        matched = list(client.scan_iter(match=f"camera:*:{config.CAMERA_ID}:source_url"))
        if matched:
            key = matched[0]  # 슬롯당 현장 하나만 활성화
            url   = client.get(key)
            type_ = client.get(key.replace(":source_url", ":source_type"))
            # key 형식: camera:{site_id}:{cam_id}:source_url
            parts   = key.split(":")
            site_id = parts[1] if len(parts) >= 4 else ""
            if url and type_:
                logger.info("소스 수신 (type=%s url=%s site_id=%s)", type_, url, site_id)
                return url, type_, site_id
        time.sleep(2)


def main():
    client = get_client()
    if config.SOURCE_PATH and config.SOURCE_TYPE:
        source_path, source_type, site_id = config.SOURCE_PATH, config.SOURCE_TYPE, ""
    else:
        source_path, source_type, site_id = wait_for_source()

    while True:
        cls = _SOURCES.get(source_type)
        if cls is None:
            raise ValueError(f"지원하지 않는 SOURCE_TYPE: {source_type}")

        source = cls()
        source.open(source_path)

        realtime = source_type in ("youtube", "file")
        sampler   = FpsSampler(source, realtime=realtime)
        publisher = FramePublisher(site_id=site_id)

        # 존재 확인에 사용할 Redis 키 (새 포맷 우선)
        active_key = (
            f"camera:{site_id}:{config.CAMERA_ID}:source_url"
            if site_id
            else f"camera:{config.CAMERA_ID}:source_url"
        )

        check_interval = max(1, int(config.SAMPLE_FPS) * 5)  # 5초마다 확인
        for i, frame in enumerate(sampler.frames()):
            if i % check_interval == 0:
                if not client.exists(active_key):
                    logger.info("소스 키 삭제됨, ingestion 종료 (camera_id=%s)", config.CAMERA_ID)
                    break
            publisher.publish(frame)

        source.close()

        if source_type == "file":
            current_url = client.get(active_key)
            if current_url == source_path:
                client.delete(active_key)
                client.delete(active_key.replace(":source_url", ":source_type"))
                logger.info("파일 재생 완료, 다음 소스 대기 (camera_id=%s)", config.CAMERA_ID)
            else:
                logger.info(
                    "파일 재생 완료, 소스가 변경됨 → 새 소스로 전환 (camera_id=%s, new_url=%s)",
                    config.CAMERA_ID, current_url,
                )

        source_path, source_type, site_id = wait_for_source()


if __name__ == "__main__":
    main()
