# 독립 프로세스를 띄워 서비스를 시작하는 진입점.
# 정의: main() — multiprocessing.Process로 unified pipeline을 실행.
# 입력: 없음 (각 프로세스가 Redis에서 직접 읽음).
# 출력: 없음 (프로세스들이 종료될 때까지 블로킹).

import multiprocessing
import logging

from pipelines.s0_unified import run as unified_run
from pipelines.s9_cleaner import cleaner_process
from redis_client import init_consumer_groups

logging.basicConfig(level=logging.INFO, format="%(processName)s %(levelname)s %(message)s")

WORKERS = [
    ("unified", unified_run),
    ("cleaner", cleaner_process),
]


def main():
    init_consumer_groups()
    
    processes = [
        multiprocessing.Process(target=fn, name=name, daemon=True)
        for name, fn in WORKERS
    ]

    for p in processes:
        p.start()
        logging.info("started %s (pid=%d)", p.name, p.pid)

    # 하나라도 죽으면 전체 종료
    try:
        while True:
            for p in processes:
                p.join(timeout=1)
                if not p.is_alive():
                    logging.error("%s exited (code=%s) — shutting down", p.name, p.exitcode)
                    for other in processes:
                        other.terminate()
                    for other in processes:
                        other.join()  # 추가
                    return
    except KeyboardInterrupt:
        logging.info("interrupted — shutting down")
        for p in processes:
            p.terminate()
        for p in processes:
            p.join()  # 추가


if __name__ == "__main__":
    main()
