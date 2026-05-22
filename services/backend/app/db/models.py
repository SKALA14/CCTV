import uuid
from datetime import datetime

from sqlalchemy import JSON, String, Text, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from pgvector.sqlalchemy import Vector

from app.db.session import Base


class CctvChannel(Base):
    __tablename__ = "cctv_channels"

    camera_id:   Mapped[str]      = mapped_column(String(50), primary_key=True)
    camera_name: Mapped[str]      = mapped_column(String(100), nullable=False)
    source_type: Mapped[str]      = mapped_column(String(20), nullable=False)
    source_url:  Mapped[str]      = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    created_at:  Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class EventLog(Base):
    # camera_id는 FK 없이 단순 문자열로 보관 — 채널이 삭제돼도 이벤트 이력을 보존하기 위함.
    __tablename__ = "event_logs"

    event_id:     Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    camera_id:    Mapped[str]       = mapped_column(String(50), nullable=False)
    camera_name:  Mapped[str | None] = mapped_column(String(100), nullable=True)  # 발생 시점의 채널 이름 (snapshot)
    pipeline:     Mapped[str]       = mapped_column(String(20), nullable=False)
    event_type:   Mapped[str]       = mapped_column(String(50), nullable=False)
    danger_level: Mapped[str]       = mapped_column(String(10), nullable=False)
    description:  Mapped[str | None] = mapped_column(Text)
    source_path:  Mapped[str | None] = mapped_column(Text)
    frame_path:   Mapped[str | None] = mapped_column(Text)
    thumbnail_url: Mapped[str | None] = mapped_column(Text)
    snapshot_urls: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    clip_url:      Mapped[str | None] = mapped_column(Text)
    confidence:   Mapped[float | None] = mapped_column(nullable=True)
    source_model: Mapped[str | None] = mapped_column(String(50))
    occurred_at:  Mapped[datetime]  = mapped_column(DateTime(timezone=True), nullable=False)
    created_at:   Mapped[datetime]  = mapped_column(DateTime(timezone=True), server_default=func.now())
    embedding:    Mapped[list[float] | None] = mapped_column(Vector(1536))