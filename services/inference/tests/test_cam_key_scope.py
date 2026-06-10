# services/inference/tests/test_cam_key_scope.py
"""compound cam_key 기반 site 스코프 키/경로 검증."""
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))


def test_split_cam_key_with_site():
    from vlm.client import _split_cam_key
    assert _split_cam_key("site-abc:cam0") == ("site-abc", "cam0")


def test_split_cam_key_legacy_no_site():
    from vlm.client import _split_cam_key
    assert _split_cam_key("cam0") == ("", "cam0")


def test_categories_key_site_scoped_no_zone():
    from vlm.client import _get_categories_key
    with patch("vlm.client.get_client") as mock_client:
        mock_client.return_value.get.return_value = None  # zone 없음
        key = _get_categories_key("static", "site-abc:cam0")
    assert key == "checklist:site-abc:static:categories"


def test_categories_key_site_scoped_with_zone():
    from vlm.client import _get_categories_key
    with patch("vlm.client.get_client") as mock_client:
        mock_client.return_value.get.return_value = "용접 구역"
        key = _get_categories_key("dynamic", "site-abc:cam1")
    assert key == "checklist:site-abc:zone_용접_구역:dynamic:categories"


def test_categories_key_legacy_no_site():
    from vlm.client import _get_categories_key
    with patch("vlm.client.get_client") as mock_client:
        mock_client.return_value.get.return_value = None
        key = _get_categories_key("static", "cam0")
    assert key == "checklist:static:categories"


def test_load_checklist_reads_site_scoped_file(tmp_path, monkeypatch):
    from vlm import client
    monkeypatch.setattr(client.config, "CHECKLIST_DIR", str(tmp_path))
    site_dir = tmp_path / "site-abc"
    site_dir.mkdir()
    (site_dir / "static_checklist.md").write_text("1. 안전모 착용", encoding="utf-8")
    with patch("vlm.client.get_client") as mock_client:
        mock_client.return_value.get.return_value = None  # zone 없음
        text = client._load_checklist("static", "site-abc:cam0")
    assert text == "1. 안전모 착용"


def test_load_checklist_prefers_zone_file(tmp_path, monkeypatch):
    from vlm import client
    monkeypatch.setattr(client.config, "CHECKLIST_DIR", str(tmp_path))
    site_dir = tmp_path / "site-abc"
    site_dir.mkdir()
    (site_dir / "static_checklist.md").write_text("글로벌", encoding="utf-8")
    (site_dir / "zone_용접_구역_static.md").write_text("용접 체크", encoding="utf-8")
    with patch("vlm.client.get_client") as mock_client:
        mock_client.return_value.get.return_value = "용접 구역"  # 구역 있음
        text = client._load_checklist("static", "site-abc:cam0")
    assert text == "용접 체크"


def test_load_checklist_missing_file_returns_empty(tmp_path, monkeypatch):
    from vlm import client
    monkeypatch.setattr(client.config, "CHECKLIST_DIR", str(tmp_path))
    with patch("vlm.client.get_client") as mock_client:
        mock_client.return_value.get.return_value = None
        text = client._load_checklist("static", "site-none:cam0")
    assert text == ""
