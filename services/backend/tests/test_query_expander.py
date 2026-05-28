import json
from unittest.mock import AsyncMock, MagicMock, patch
import pytest


@pytest.mark.asyncio
async def test_expand_query_returns_variants():
    mock_resp = MagicMock()
    mock_resp.choices[0].message.content = '["불", "화재", "연기", "화염", "불꽃"]'

    with patch("app.api.query_expander._openai") as mock_openai:
        mock_openai.chat.completions.create = AsyncMock(return_value=mock_resp)
        from app.api.query_expander import expand_query
        result = await expand_query("불")

    assert "불" in result
    assert "화재" in result
    assert len(result) <= 5


@pytest.mark.asyncio
async def test_expand_query_fallback_on_error():
    with patch("app.api.query_expander._openai") as mock_openai:
        mock_openai.chat.completions.create = AsyncMock(side_effect=Exception("API 오류"))
        from app.api.query_expander import expand_query
        result = await expand_query("낙상")

    assert result == ["낙상"]


@pytest.mark.asyncio
async def test_expand_query_fallback_on_invalid_json():
    mock_resp = MagicMock()
    mock_resp.choices[0].message.content = "유효하지 않은 응답"

    with patch("app.api.query_expander._openai") as mock_openai:
        mock_openai.chat.completions.create = AsyncMock(return_value=mock_resp)
        from app.api.query_expander import expand_query
        result = await expand_query("침입")

    assert result == ["침입"]
