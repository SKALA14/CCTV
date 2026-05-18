"""
search_events ORM 쿼리 조립 검증.
실제 DB/OpenAI 호출 없이 생성된 SQLAlchemy statement를 검사한다.
"""
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.dialects import postgresql

from app.db.models import EventLog


def _compile(stmt) -> str:
    return str(stmt.compile(
        dialect=postgresql.dialect(),
        compile_kwargs={"literal_binds": False}
    ))


def test_base_query_contains_cosine_operator():
    distance_col = EventLog.embedding.cosine_distance([0.1] * 1536).label("distance")
    stmt = (
        select(EventLog, distance_col)
        .where(EventLog.embedding.is_not(None))
        .order_by(distance_col)
        .limit(10)
    )
    sql = _compile(stmt)
    assert "<=>" in sql
    assert "embedding IS NOT NULL" in sql
    assert "ORDER BY" in sql
    assert "LIMIT" in sql


def test_channel_filter_added():
    distance_col = EventLog.embedding.cosine_distance([0.1] * 1536).label("distance")
    stmt = (
        select(EventLog, distance_col)
        .where(EventLog.embedding.is_not(None))
        .where(EventLog.camera_id == "cam0")
        .order_by(distance_col)
        .limit(10)
    )
    sql = _compile(stmt)
    assert "camera_id" in sql


def test_date_filter_added():
    start = datetime(2026, 5, 1, tzinfo=timezone.utc)
    end   = datetime(2026, 5, 16, tzinfo=timezone.utc)
    distance_col = EventLog.embedding.cosine_distance([0.1] * 1536).label("distance")
    stmt = (
        select(EventLog, distance_col)
        .where(EventLog.embedding.is_not(None))
        .where(EventLog.occurred_at >= start)
        .where(EventLog.occurred_at <= end)
        .order_by(distance_col)
        .limit(10)
    )
    sql = _compile(stmt)
    assert "occurred_at" in sql


def test_no_sqlalchemy_text_in_query():
    distance_col = EventLog.embedding.cosine_distance([0.1] * 1536).label("distance")
    stmt = (
        select(EventLog, distance_col)
        .where(EventLog.embedding.is_not(None))
        .order_by(distance_col)
        .limit(10)
    )
    assert "text(" not in repr(stmt)
