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
    thumbnail_url: str | None
    clip_url:      str | None
    source_path:   str | None
    occurred_at:   datetime
    created_at:    datetime


class EventListResponse(BaseModel):
    events: list[EventLogRead]
    total:  int
    skip:   int
    limit:  int