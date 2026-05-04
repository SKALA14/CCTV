# API 요청/응답 스키마 정의 파일. DB 모델과 분리하여 프론트엔드가 기대하는 필드명과 구조로 응답을 구성한다.
# API 요청/응답 구조

import uuid
from datetime import datetime

from pydantic import BaseModel


# 단건 이벤트 응답 스키마. DB의 EventLog를 프론트엔드 필드명에 맞게 변환한 형태.
class EventLogRead(BaseModel):
    id:            uuid.UUID
    channel_id:    str
    channel_name:  str | None
    pipeline:      str
    event_type:    str
    danger_level:  str
    reason:        str | None
    confidence:    float | None
    vlm_confidence: float | None
    pose_event:    str | None
    thumbnail_url: str | None
    clip_url:      str | None
    source_path:   str | None
    occurred_at:   datetime
    created_at:    datetime


# 이벤트 목록 응답 스키마. 이벤트 배열과 페이지네이션 정보를 함께 반환한다.
class EventListResponse(BaseModel):
    events: list[EventLogRead]
    total:  int
    skip:   int
    limit:  int
