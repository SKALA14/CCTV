from unittest.mock import AsyncMock, MagicMock, patch
import pytest


@pytest.mark.asyncio
async def test_describe_for_embedding_returns_llm_text():
    mock_resp = MagicMock()
    mock_resp.choices[0].message.content = "낙상 사고 발생. 작업자가 바닥에 쓰러짐. 추락, fall, 넘어짐."

    with patch("app.api.embed_describer._openai") as mock_openai:
        mock_openai.chat.completions.create = AsyncMock(return_value=mock_resp)
        from app.api.embed_describer import describe_for_embedding
        result = await describe_for_embedding("fall", "high", "작업자가 계단에서 미끄러짐")

    assert "낙상" in result
    assert "fall" in result


@pytest.mark.asyncio
async def test_describe_for_embedding_fallback_on_error():
    with patch("app.api.embed_describer._openai") as mock_openai:
        mock_openai.chat.completions.create = AsyncMock(side_effect=Exception("API 오류"))
        from app.api.embed_describer import describe_for_embedding
        result = await describe_for_embedding("fire", "critical", "연기 감지")

    assert result == "fire critical 연기 감지"
