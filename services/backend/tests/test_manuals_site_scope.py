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


def test_effective_site_id_always_own_site():
    """admin/user 2단계 — 모든 계정은 자기 현장. site_id 파라미터는 무시."""
    from app.api import manuals

    own = uuid.uuid4()

    class _U:
        role = "admin"
        site_id = own

    assert manuals._effective_site_id(_U(), "ignored") == own
    assert manuals._effective_site_id(_U(), None) == own

    class _UserRole:
        role = "user"
        site_id = own

    assert manuals._effective_site_id(_UserRole(), "ignored") == own
