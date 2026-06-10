# services/inference/schema.py
"""Inference 서비스 전역에서 공유하는 작업/결과 타입 정의."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np


@dataclass
class FrameJob:
    """Redis frames stream에서 읽은 프레임 단위 작업."""
    msg_id: str
    camera_id: str
    frame_path: str
    timestamp: str
    site_id: str = ""   # 현장 격리용 — alerts 발행/현장별 dedup에 사용
    frame: Optional[np.ndarray] = field(default=None, compare=False, repr=False)


@dataclass(frozen=True)
class ModelResult:
    """Emergency 모델 worker가 aggregator로 반환하는 결과."""
    msg_id: str
    model_name: str
    detections: list[dict]
    error: str = ""


@dataclass
class PendingFrame:
    """Emergency aggregator가 msg_id별로 진행 상태를 추적하기 위한 상태."""
    job: FrameJob
    started_at: float
    expected_models: set[str] = field(default_factory=set)
    received_models: set[str] = field(default_factory=set)
    detections: list[dict] = field(default_factory=list)
    alerted_keys: set[str] = field(default_factory=set)
