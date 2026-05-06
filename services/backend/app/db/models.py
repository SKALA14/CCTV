import uuid
from datetime import datetime

from sqlalchemy import String, Text, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from pgvector.sqlalchemy import Vector

from app.db.session import Base


class CctvChannel(Base):
    __tablename__ = "cctv_channels"

    camera_id:   Mapped[str]      = mapped_column(String(50), primary_key=True)
    camera_name: Mapped[str]      = mapped_column(String(100), nullable=False)
    source_type: Mapped[str]      = mapped_column(String(20), nullable=False)
    source_url:  Mapped[str]      = mapped_column(Text, nullable=False)
    created_at:  Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    events: Mapped[list["EventLog"]] = relationship(back_populates="channel")


class EventLog(Base):
    __tablename__ = "event_logs"

    event_id:     Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    camera_id:    Mapped[str]       = mapped_column(String(50), ForeignKey("cctv_channels.camera_id"), nullable=False)
    pipeline:     Mapped[str]       = mapped_column(String(20), nullable=False)
    event_type:   Mapped[str]       = mapped_column(String(50), nullable=False)
    danger_level: Mapped[str]       = mapped_column(String(10), nullable=False)
    description:  Mapped[str | None] = mapped_column(Text)
    source_path:  Mapped[str | None] = mapped_column(Text)
    occurred_at:  Mapped[datetime]  = mapped_column(DateTime(timezone=True), nullable=False)
    created_at:   Mapped[datetime]  = mapped_column(DateTime(timezone=True), server_default=func.now())
    embedding:    Mapped[list[float] | None] = mapped_column(Vector(1536))

    channel: Mapped["CctvChannel"] = relationship(back_populates="events")