'''
unified pipeline에서 공유하는 작업/결과 상태 타입을 정의한다.

입력 흐름
- Redis frames 메시지 스키마: {frame_path: str, camera_id: str, timestamp: str}
- unified.py는 Redis msg_id를 그대로 FrameJob.msg_id로 사용한다.

출력/전달 흐름
- FrameJob: dispatcher가 모델별 queue에 넣는 작업 단위
- ModelResult: 모델 worker가 result_queue로 반환하는 결과 단위
- PendingFrame: aggregator가 msg_id별 진행 상태를 추적하는 내부 상태
'''

from dataclasses import dataclass, field


@dataclass(frozen=True)
class FrameJob:
    # msg_id는 Redis ACK와 모델별 결과 취합에 모두 사용하는 프레임 작업 ID다.
    msg_id: str
    camera_id: str
    frame_path: str
    timestamp: str


@dataclass(frozen=True)
class ModelResult:
    # detections 원소 스키마:
    # {route: "emergency"|"general", anomaly_type: str, confidence: float, source_model: str, ...}
    msg_id: str
    model_name: str
    detections: list[dict]
    error: str = ""


@dataclass
class PendingFrame:
    # expected_models와 received_models를 비교해 모든 모델 완료 또는 timeout 여부를 판단한다.
    job: FrameJob
    started_at: float
    expected_models: set[str] = field(default_factory=set)
    received_models: set[str] = field(default_factory=set)
    detections: list[dict] = field(default_factory=list)
    has_general_candidate: bool = False
    alerted_keys: set[str] = field(default_factory=set)
