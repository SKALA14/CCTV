# services/backend/tests/test_auth.py
import pytest
import uuid
from unittest.mock import MagicMock, patch


def _make_settings(**kwargs):
    """테스트용 config 오버라이드."""
    m = MagicMock()
    m.AUTH_SECRET            = "test-secret-key-32chars-for-tests!"
    m.SITE_NAME              = "default"
    m.ADMIN_USERNAME         = "admin"
    m.ADMIN_PASSWORD         = "admin1234!"
    m.JWT_EXPIRE_HOURS       = 1
    m.REDIS_URL              = "redis://localhost:6379"
    m.COOKIE_SECURE          = False
    for k, v in kwargs.items():
        setattr(m, k, v)
    return m


@pytest.mark.asyncio
async def test_create_token_contains_site_id(monkeypatch):
    import app.api.auth as auth_module

    async def mock_get_boot_id():
        return "test-boot-id"

    monkeypatch.setattr(auth_module, "_get_boot_id", mock_get_boot_id)

    with patch("app.api.auth.config", _make_settings()):
        site_id = uuid.uuid4()
        token = await auth_module._create_token(
            user_id=uuid.uuid4(), username="admin_user", role="admin", site_id=site_id
        )
        payload = auth_module._decode_token(token)

    assert payload["role"] == "admin"
    assert payload["site_id"] == str(site_id)
    assert payload["bid"] == "test-boot-id"


@pytest.mark.asyncio
async def test_create_token_omits_none_site_id(monkeypatch):
    import app.api.auth as auth_module

    async def mock_get_boot_id():
        return "test-boot-id"

    monkeypatch.setattr(auth_module, "_get_boot_id", mock_get_boot_id)

    with patch("app.api.auth.config", _make_settings()):
        token = await auth_module._create_token(
            user_id=uuid.uuid4(), username="admin", role="admin", site_id=None
        )
        payload = auth_module._decode_token(token)

    assert payload["role"] == "admin"
    assert payload.get("site_id") is None


@pytest.mark.asyncio
async def test_create_token_sub_is_user_id(monkeypatch):
    import app.api.auth as auth_module

    async def mock_get_boot_id():
        return "test-boot-id"

    monkeypatch.setattr(auth_module, "_get_boot_id", mock_get_boot_id)

    with patch("app.api.auth.config", _make_settings()):
        user_id = uuid.uuid4()
        token = await auth_module._create_token(
            user_id=user_id, username="normal_user", role="user", site_id=uuid.uuid4()
        )
        payload = auth_module._decode_token(token)

    assert payload["sub"] == str(user_id)


def test_decode_token_invalid_raises():
    from fastapi import HTTPException
    with patch("app.api.auth.config", _make_settings()):
        from app.api.auth import _decode_token
        with pytest.raises(HTTPException) as exc_info:
            _decode_token("invalid.token.here")
    assert exc_info.value.status_code == 401
