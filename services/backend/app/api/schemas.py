import uuid
from datetime import datetime

from pydantic import BaseModel


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
    source_model:  str | None
    frame_path:    str | None
    thumbnail_url: str | None
    snapshot_urls: list[str] | None = None
    clip_url:      str | None
    source_path:   str | None
    occurred_at:   datetime
    created_at:    datetime
    similarity:    float | None = None
    incident_count:   int = 1                  # incident 안의 raw event 수 (1 = 단일)
    incident_last_at: datetime | None = None   # incident 마지막 이벤트 시각 (None = occurred_at과 동일)


class EventListResponse(BaseModel):
    events:         list[EventLogRead]
    total:          int
    skip:           int
    limit:          int
    applied_filter: str | None = None