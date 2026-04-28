# delete_queue에서 파일 경로를 꺼내 로컬 디스크에서 삭제하는 프로세스를 정의한다.
# 정의: cleaner_process() — 무한루프로 BLPOP 대기 후 파일 삭제.
# 입력: Redis 리스트 "delete_queue" (mark_processed가 채움), 각 원소는 JPEG 절대경로.
# 출력: 없음 (부수효과: 파일시스템에서 프레임 파일 제거).

import os
import logging
from redis_client import get_client

logger = logging.getLogger(__name__)

def cleaner_process():
    r = get_client()
    while True:
        result = r.blpop("delete_queue", timeout=5)
        if result:
            _, path = result
            if os.path.exists(path):
                try:
                    os.remove(path)
                    logger.info("deleted %s", path)
                except OSError as e:
                    logger.error("failed to delete %s: %s", path, e)