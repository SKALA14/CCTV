# services/backend/tests/test_db_channel_to_dict.py
"""DB CctvChannel → 프론트 채널 dict 매핑 검증."""


class _FakeChannel:
    def __init__(self, camera_id, camera_name, source_type, source_url, description=None):
        self.camera_id = camera_id
        self.camera_name = camera_name
        self.source_type = source_type
        self.source_url = source_url
        self.description = description


def test_maps_cam_id_to_slot():
    from app.api.channels import _db_channel_to_dict
    ch = _FakeChannel("cam2", "정문", "rtsp", "rtsp://mediamtx:8554/x")
    result = _db_channel_to_dict(ch)
    assert result["slot"] == 2
    assert result["name"] == "정문"
    assert result["channelName"] == "정문"
    assert result["sourceType"] == "rtsp"
    assert result["rtspUrl"] == "rtsp://mediamtx:8554/x"
    assert result["ingestion_url"] == "rtsp://mediamtx:8554/x"


def test_description_none_becomes_empty_string():
    from app.api.channels import _db_channel_to_dict
    ch = _FakeChannel("cam0", "후문", "file", "/sample/a.mp4", None)
    result = _db_channel_to_dict(ch)
    assert result["description"] == ""
    assert result["slot"] == 0


def test_non_cam_prefixed_id_defaults_slot_zero():
    from app.api.channels import _db_channel_to_dict
    ch = _FakeChannel("weird", "x", "rtsp", "u")
    assert _db_channel_to_dict(ch)["slot"] == 0
