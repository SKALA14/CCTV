# services/backend/tests/test_manuals_site_scope.py
"""메뉴얼 site 스코프 헬퍼 검증."""
import uuid


def test_site_dir_creates_subdir(tmp_path, monkeypatch):
    from app.api import manuals
    monkeypatch.setattr(manuals.config, "PROMPTS_DIR", str(tmp_path))
    sid = "11111111-1111-1111-1111-111111111111"
    d = manuals._site_dir(sid)
    assert d.exists()
    assert d.name == sid
    assert d.parent == tmp_path


def test_effective_site_id_superadmin_uses_param():
    from app.api import manuals

    class _U:
        role = "superadmin"
        site_id = None

    sid = uuid.uuid4()
    assert manuals._effective_site_id(_U(), str(sid)) == sid
    assert manuals._effective_site_id(_U(), None) is None


def test_effective_site_id_admin_uses_own_site():
    from app.api import manuals

    own = uuid.uuid4()

    class _U:
        role = "admin"
        site_id = own

    assert manuals._effective_site_id(_U(), "ignored") == own


def test_effective_site_id_superadmin_invalid_param_returns_none():
    from app.api import manuals

    class _U:
        role = "superadmin"
        site_id = None

    assert manuals._effective_site_id(_U(), "not-a-uuid") is None
