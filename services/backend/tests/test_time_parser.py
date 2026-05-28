from datetime import datetime, timezone
from unittest.mock import patch
import pytest

# 고정 기준 시각: 2026-05-16 (금요일) 12:00:00 UTC
FIXED_NOW = datetime(2026, 5, 16, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def mock_now():
    with patch("app.api.time_parser._now", return_value=FIXED_NOW):
        yield


def test_no_time_expression():
    from app.api.time_parser import parse_time_expression
    cleaned, start, end, label = parse_time_expression("작업자 넘어짐")
    assert cleaned == "작업자 넘어짐"
    assert start is None
    assert end is None
    assert label is None


def test_오늘():
    from app.api.time_parser import parse_time_expression
    cleaned, start, end, label = parse_time_expression("오늘 화재 발생")
    assert cleaned == "화재 발생"
    assert start == datetime(2026, 5, 16, 0, 0, 0, tzinfo=timezone.utc)
    assert end == FIXED_NOW
    assert label == "오늘 필터 적용됨"


def test_어제():
    from app.api.time_parser import parse_time_expression
    cleaned, start, end, label = parse_time_expression("어제 작업자 넘어짐")
    assert cleaned == "작업자 넘어짐"
    assert start == datetime(2026, 5, 15, 0, 0, 0, tzinfo=timezone.utc)
    assert end == datetime(2026, 5, 15, 23, 59, 59, 999999, tzinfo=timezone.utc)
    assert label == "어제 필터 적용됨"


def test_이번_주():
    from app.api.time_parser import parse_time_expression
    cleaned, start, end, label = parse_time_expression("이번 주 안전모 미착용")
    assert cleaned == "안전모 미착용"
    assert start == datetime(2026, 5, 11, 0, 0, 0, tzinfo=timezone.utc)  # 월요일
    assert end == FIXED_NOW
    assert label == "이번 주 필터 적용됨"


def test_저번_주():
    from app.api.time_parser import parse_time_expression
    cleaned, start, end, label = parse_time_expression("저번 주 작업자 넘어진 상황 있어")
    assert cleaned == "작업자 넘어진 상황 있어"
    assert start == datetime(2026, 5, 4, 0, 0, 0, tzinfo=timezone.utc)
    assert end == datetime(2026, 5, 10, 23, 59, 59, 999999, tzinfo=timezone.utc)
    assert label == "저번 주 필터 적용됨"


def test_지난_주_alias():
    from app.api.time_parser import parse_time_expression
    cleaned, start, end, label = parse_time_expression("지난 주 화재")
    assert start == datetime(2026, 5, 4, 0, 0, 0, tzinfo=timezone.utc)
    assert label == "저번 주 필터 적용됨"


def test_지난_N일():
    from app.api.time_parser import parse_time_expression
    cleaned, start, end, label = parse_time_expression("지난 3일 화재")
    assert cleaned == "화재"
    assert start == datetime(2026, 5, 13, 0, 0, 0, tzinfo=timezone.utc)
    assert end == FIXED_NOW
    assert label == "지난 3일 필터 적용됨"


def test_N일_전():
    from app.api.time_parser import parse_time_expression
    cleaned, start, end, label = parse_time_expression("5일 전 침입 감지")
    assert cleaned == "침입 감지"
    assert start == datetime(2026, 5, 11, 0, 0, 0, tzinfo=timezone.utc)
    assert label == "지난 5일 필터 적용됨"


def test_이번_달():
    from app.api.time_parser import parse_time_expression
    cleaned, start, end, label = parse_time_expression("이번 달 이벤트")
    assert cleaned == "이벤트"
    assert start == datetime(2026, 5, 1, 0, 0, 0, tzinfo=timezone.utc)
    assert end == FIXED_NOW
    assert label == "이번 달 필터 적용됨"


def test_지난_달():
    from app.api.time_parser import parse_time_expression
    cleaned, start, end, label = parse_time_expression("지난 달 화재")
    assert cleaned == "화재"
    assert start == datetime(2026, 4, 1, 0, 0, 0, tzinfo=timezone.utc)
    assert end == datetime(2026, 4, 30, 23, 59, 59, 999999, tzinfo=timezone.utc)
    assert label == "지난 달 필터 적용됨"


def test_query_only_time_expression():
    from app.api.time_parser import parse_time_expression
    cleaned, start, end, label = parse_time_expression("어제")
    assert cleaned == ""
    assert label == "어제 필터 적용됨"
