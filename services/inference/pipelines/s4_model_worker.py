'''
모델별 worker를 실행해 FrameJob을 소비하고 ModelResult를 결과 큐로 전달한다.

입력
- input_queue: FrameJob 또는 종료 신호(None)가 들어오는 모델별 queue.
- FrameJob 스키마: {msg_id, camera_id, frame_path, timestamp}
- model_factory: FireYOLO, PoseYOLO, GeneralYOLO 등 모델 생성자.

출력
- result_queue에 ModelResult를 push한다.
- ModelResult 스키마: {msg_id, model_name, detections, error}
- detections는 모델별 predict(frame, h, w)가 반환한 route 기반 detection 목록이다.
'''

import logging
import queue
from typing import Callable

import cv2

from pipelines.s1_types import FrameJob, ModelResult

logger = logging.getLogger(__name__)


def model_worker(
    model_name: str,
    model_factory: Callable[[], object],
    input_queue: "queue.Queue[FrameJob | None]",
    result_queue: "queue.Queue[ModelResult]",
) -> None:
    # 모델은 worker 시작 시 1회만 로드하고, 이후에는 FrameJob만 계속 소비한다.
    model = model_factory()
    logger.info("%s model worker started", model_name)

    while True:
        job = input_queue.get()
        if job is None:
            input_queue.task_done()
            break

        try:
            frame = cv2.imread(job.frame_path)
            if frame is None:
                detections = []
            else:
                h, w = frame.shape[:2]
                detections = model.predict(frame, h, w)
            result = ModelResult(job.msg_id, model_name, detections)
        except Exception as exc:
            logger.exception("%s model worker error: msg_id=%s", model_name, job.msg_id)
            result = ModelResult(job.msg_id, model_name, [], str(exc))

        result_queue.put(result)
        input_queue.task_done()
