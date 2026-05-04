# DB 테이블 정의 파일. cctv_channels(카메라 정보)와 event_logs(이벤트 로그) 테이블을 ORM 클래스로 정의한다.
# PostgreSQL 테이블 구조

import uuid
from datetime import datetime

from sqlalchemy import String, Text, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from pgvector.sqlalchemy import Vector

from app.db import Base


# CCTV 채널(카메라) 정보 저장하는 테이블 : event_logs의 camera_id가 이 테이블 참조
class CctvChannel(Base):
    __tablename__ = "cctv_channels"

    camera_id:   Mapped[str]      = mapped_column(String(50), primary_key=True)
    camera_name: Mapped[str]      = mapped_column(String(100), nullable=False)
    source_type: Mapped[str]      = mapped_column(String(20), nullable=False)
    source_url:  Mapped[str]      = mapped_column(Text, nullable=False)
    created_at:  Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    events: Mapped[list["EventLog"]] = relationship(back_populates="channel")


# 이상 탐지 이벤트 저장 테이블 : emergency/general 파이프라인 결과 저장
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
    # 의미 기반 검색을 위한 description 임베딩 벡터 (OpenAI text-embedding-3-small, 1536차원).
    embedding:    Mapped[list[float] | None] = mapped_column(Vector(1536))

    channel: Mapped["CctvChannel"] = relationship(back_populates="events")
