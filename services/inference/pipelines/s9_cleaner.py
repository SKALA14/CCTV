'''
프레임 처리 완료 후 delete_queue에 등록된 JPEG 파일을 디스크에서 삭제하는 정리 파이프라인이다.

입력
- Redis 리스트 delete_queue: ack_frame()이 frame_path를 push한다.
- 각 원소는 ingestion이 저장한 JPEG 파일 경로다.

출력/부수효과
- 해당 frame_path가 존재하면 os.remove()로 삭제한다.
- 파일이 이미 없으면 별도 처리 없이 다음 작업을 기다린다.
'''

import logging
import os

from redis_client import get_client

logger = logging.getLogger(__name__)


def cleaner_process() -> None:
    r = get_client()
    while True:
        result = r.blpop("delete_queue", timeout=5)
        if not result:
            continue

        _, path = result
        if not os.path.exists(path):
            continue

        try:
            os.remove(path)
            logger.info("deleted %s", path)
        except OSError as exc:
            logger.error("failed to delete %s: %s", path, exc)
