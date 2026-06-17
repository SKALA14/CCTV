# services/backend/app/db/models.py
"""ORM 모델 정의 — sites / users / cctv_channels / event_logs 테이블."""

import uuid
from datetime import datetime

from sqlalchemy import JSON, String, Text, DateTime, Boolean, ForeignKey, UniqueConstraint, CheckConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from pgvector.sqlalchemy import Vector

from app.db.session import Base


class Site(Base):
    __tablename__ = "sites"

    id:         Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name:       Mapped[str]       = mapped_column(String(100), nullable=False, unique=True)
    created_at: Mapped[datetime]  = mapped_column(DateTime(timezone=True), server_default=func.now())


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "role IN ('admin', 'user') AND site_id IS NOT NULL",
            name="ck_user_site_role",
        ),
    )

    id:                   Mapped[uuid.UUID]      = mapped_column(primary_key=True, default=uuid.uuid4)
    username:             Mapped[str]            = mapped_column(String(50), nullable=False, unique=True)
    hashed_password:      Mapped[str]            = mapped_column(String(255), nullable=False)
    role:                 Mapped[str]            = mapped_column(String(20), nullable=False)
    site_id:              Mapped[uuid.UUID | None] = mapped_column(
                              ForeignKey("sites.id", ondelete="CASCADE"), nullable=True
                          )
    must_change_password: Mapped[bool]           = mapped_column(Boolean, nullable=False, default=True)
    created_at:           Mapped[datetime]       = mapped_column(DateTime(timezone=True), server_default=func.now())


class CctvChannel(Base):
    __tablename__ = "cctv_channels"
    __table_args__ = (
        UniqueConstraint("camera_id", "site_id", name="uq_channel_per_site"),
    )

    id:          Mapped[uuid.UUID]      = mapped_column(primary_key=True, default=uuid.uuid4)
    site_id:     Mapped[uuid.UUID]      = mapped_column(
                     ForeignKey("sites.id", ondelete="CASCADE"), nullable=False
                 )
    camera_id:   Mapped[str]            = mapped_column(String(50), nullable=False)
    camera_name: Mapped[str]            = mapped_column(String(100), nullable=False)
    source_type: Mapped[str]            = mapped_column(String(20), nullable=False)
    source_url:  Mapped[str]            = mapped_column(Text, nullable=False)
    description: Mapped[str | None]    = mapped_column(Text)
    created_at:  Mapped[datetime]       = mapped_column(DateTime(timezone=True), server_default=func.now())


class EventLog(Base):
    # camera_id는 FK 없이 단순 문자열로 보관 — 채널이 삭제돼도 이벤트 이력을 보존하기 위함.
    __tablename__ = "event_logs"

    event_id:     Mapped[uuid.UUID]       = mapped_column(primary_key=True, default=uuid.uuid4)
    site_id:      Mapped[uuid.UUID | None] = mapped_column(
                      ForeignKey("sites.id", ondelete="SET NULL"), nullable=True
                  )
    camera_id:    Mapped[str]             = mapped_column(String(50), nullable=False)
    camera_name:  Mapped[str | None]      = mapped_column(String(100), nullable=True)
    pipeline:     Mapped[str]             = mapped_column(String(20), nullable=False)
    event_type:   Mapped[str]             = mapped_column(String(50), nullable=False)
    danger_level: Mapped[str]             = mapped_column(String(10), nullable=False)
    description:  Mapped[str | None]      = mapped_column(Text)
    source_path:  Mapped[str | None]      = mapped_column(Text)
    frame_path:   Mapped[str | None]      = mapped_column(Text)
    thumbnail_url: Mapped[str | None]     = mapped_column(Text)
    snapshot_urls: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    clip_url:      Mapped[str | None]     = mapped_column(Text)
    source_model: Mapped[str | None]      = mapped_column(String(50))
    occurred_at:  Mapped[datetime]        = mapped_column(DateTime(timezone=True), nullable=False)
    created_at:   Mapped[datetime]        = mapped_column(DateTime(timezone=True), server_default=func.now())
    embedding:    Mapped[list[float] | None] = mapped_column(Vector(1536))
