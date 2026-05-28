# services/inference/main.py
"""Inference 서비스 진입점. emergency/dynamic/static/cleaner 4개 프로세스를 spawn한다."""

from __future__ import annotations

import logging
import multiprocessing
import signal
import sys

from cleaner import process as cleaner_process
from dynamic import process as dynamic_process
from emergency import process as emergency_process
from redis_client import init_consumer_groups
from static import process as static_process

logging.basicConfig(level=logging.INFO, format="%(processName)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

WORKERS = [
    ("emergency", emergency_process.run),
    ("dynamic", dynamic_process.run),
    ("static", static_process.run),
    ("cleaner", cleaner_process.run),
]


def _shutdown(processes: list[multiprocessing.Process]) -> None:
    for p in processes:
        if p.is_alive():
            p.terminate()
    for p in processes:
        p.join()


def main() -> None:
    init_consumer_groups()

    processes = [
        multiprocessing.Process(target=fn, name=name, daemon=False)
        for name, fn in WORKERS
    ]
    for p in processes:
        p.start()
        logger.info("started %s (pid=%d)", p.name, p.pid)

    def _sigint_handler(_signum, _frame):
        logger.info("SIGINT received — shutting down")
        _shutdown(processes)
        sys.exit(0)

    signal.signal(signal.SIGINT, _sigint_handler)
    signal.signal(signal.SIGTERM, _sigint_handler)

    try:
        while True:
            for p in processes:
                p.join(timeout=1)
                if not p.is_alive():
                    logger.error("%s exited (code=%s) — shutting down all", p.name, p.exitcode)
                    _shutdown(processes)
                    return
    except KeyboardInterrupt:
        _shutdown(processes)


if __name__ == "__main__":
    main()
