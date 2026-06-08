# services/backend/tests/test_auth.py
import pytest
from unittest.mock import MagicMock, patch


def _make_settings(**kwargs):
    """테스트용 config 오버라이드."""
    m = MagicMock()
    m.AUTH_SECRET      = "test-secret-key-32chars-for-tests!"
    m.ADMIN_USERNAME   = "admin"
    m.ADMIN_PASSWORD   = "admin1234!"
    m.VIEWER_USERNAME  = "viewer"
    m.VIEWER_PASSWORD  = "viewer1234!"
    m.JWT_EXPIRE_HOURS = 1
    m.REDIS_URL        = "redis://localhost:6379"
    for k, v in kwargs.items():
        setattr(m, k, v)
    return m


@pytest.mark.asyncio
async def test_create_token_contains_role(monkeypatch):
    import app.api.auth as auth_module

    async def mock_get_boot_id():
        return "test-boot-id"

    with patch("app.api.auth.config", _make_settings()):
        monkeypatch.setattr(auth_module, "_get_boot_id", mock_get_boot_id)
        token = await auth_module._create_token("admin", "admin")
    assert isinstance(token, str)
    assert len(token) > 0


@pytest.mark.asyncio
async def test_create_token_contains_bid(monkeypatch):
    import app.api.auth as auth_module

    async def mock_get_boot_id():
        return "test-boot-id"

    with patch("app.api.auth.config", _make_settings()):
        monkeypatch.setattr(auth_module, "_get_boot_id", mock_get_boot_id)
        token = await auth_module._create_token("admin", "admin")
        payload = auth_module._decode_token(token)
    assert payload["role"] == "admin"
    assert payload["bid"] == "test-boot-id"


@pytest.mark.asyncio
async def test_decode_token_returns_payload(monkeypatch):
    import app.api.auth as auth_module

    async def mock_get_boot_id():
        return "test-boot-id"

    with patch("app.api.auth.config", _make_settings()):
        monkeypatch.setattr(auth_module, "_get_boot_id", mock_get_boot_id)
        token = await auth_module._create_token("viewer", "viewer")
        payload = auth_module._decode_token(token)
    assert payload["sub"] == "viewer"
    assert payload["role"] == "viewer"


def test_decode_token_invalid_raises():
    from fastapi import HTTPException
    with patch("app.api.auth.config", _make_settings()):
        from app.api.auth import _decode_token
        with pytest.raises(HTTPException) as exc_info:
            _decode_token("invalid.token.here")
    assert exc_info.value.status_code == 401


def test_verify_credentials_admin():
    with patch("app.api.auth.config", _make_settings()):
        from app.api.auth import _verify_credentials
        result = _verify_credentials("admin", "admin1234!")
    assert result == "admin"


def test_verify_credentials_viewer():
    with patch("app.api.auth.config", _make_settings()):
        from app.api.auth import _verify_credentials
        result = _verify_credentials("viewer", "viewer1234!")
    assert result == "viewer"


def test_verify_credentials_wrong_password():
    with patch("app.api.auth.config", _make_settings()):
        from app.api.auth import _verify_credentials
        result = _verify_credentials("admin", "wrong")
    assert result is None


def test_verify_credentials_unknown_user():
    with patch("app.api.auth.config", _make_settings()):
        from app.api.auth import _verify_credentials
        result = _verify_credentials("unknown", "admin1234!")
    assert result is None
