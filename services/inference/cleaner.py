# delete_queue에서 파일 경로를 꺼내 로컬 디스크에서 삭제하는 프로세스를 정의한다.
# 정의: cleaner_process() — 무한루프로 BLPOP 대기 후 파일 삭제.
# 입력: Redis 리스트 "delete_queue" (mark_processed가 채움), 각 원소는 JPEG 절대경로.
# 출력: 없음 (부수효과: 파일시스템에서 프레임 파일 제거).
import os
from redis_client import *

def cleaner_process():
    r = get_client()
    while True:
        # delete_queue에서 경로 꺼내서 삭제
        result = r.blpop("delete_queue", timeout=5)
        if result:
            _, path = result
            if os.path.exists(path):
                os.remove(path)