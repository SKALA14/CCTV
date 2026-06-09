# services/backend/tests/test_status_helpers.py
"""Status 페이지 순수 헬퍼 검증."""


def test_latest_frame_ts_picks_max_per_camera():
    from app.api.status import _latest_frame_ts
    entries = [
        {"site_id": "s1", "camera_id": "cam0", "timestamp": "100.0"},
        {"site_id": "s1", "camera_id": "cam0", "timestamp": "150.5"},
        {"site_id": "s2", "camera_id": "cam1", "timestamp": "200.0"},
    ]
    result = _latest_frame_ts(entries)
    assert result[("s1", "cam0")] == 150.5
    assert result[("s2", "cam1")] == 200.0


def test_latest_frame_ts_skips_bad_timestamp():
    from app.api.status import _latest_frame_ts
    entries = [{"site_id": "s1", "camera_id": "cam0", "timestamp": "oops"}]
    assert _latest_frame_ts(entries) == {}


def test_is_online_within_threshold():
    from app.api.status import _is_online
    assert _is_online(100.0, now=110.0, threshold=30.0) is True


def test_is_online_beyond_threshold():
    from app.api.status import _is_online
    assert _is_online(100.0, now=200.0, threshold=30.0) is False


def test_is_online_none_is_offline():
    from app.api.status import _is_online
    assert _is_online(None, now=200.0, threshold=30.0) is False
