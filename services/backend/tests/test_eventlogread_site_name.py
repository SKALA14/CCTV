# services/backend/tests/test_eventlogread_site_name.py
"""EventLogRead에 site_name 필드가 추가되었는지 검증."""


def test_eventlogread_has_site_name_field():
    from app.api.schemas import EventLogRead
    assert "site_name" in EventLogRead.model_fields


def test_site_name_defaults_to_none():
    from app.api.schemas import EventLogRead
    field = EventLogRead.model_fields["site_name"]
    assert field.default is None
