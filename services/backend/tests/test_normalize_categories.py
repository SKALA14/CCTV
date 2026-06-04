# services/backend/tests/test_normalize_categories.py
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _make_mock_response(categories: list) -> MagicMock:
    mock_resp = MagicMock()
    mock_resp.choices[0].message.content = json.dumps(
        {"categories": categories}, ensure_ascii=False
    )
    return mock_resp


@pytest.mark.asyncio
async def test_normalize_categories_groups_similar_items():
    """의미가 유사한 항목들이 같은 카테고리로 묶이는지 확인."""
    mock_resp = _make_mock_response([
        {"code": "PPE_MISSING", "label": "보호장비 미착용",
         "items": ["안전복장 미착용인가?", "구명복 미착용인가?"]},
        {"code": "ACCESS_VIOLATION", "label": "출입통제 위반",
         "items": ["크레인 작업반경 내 무단출입인가?"]},
    ])

    with patch("app.api.agent.checklist_agent._get_openai") as mock_get:
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_resp)
        mock_get.return_value = mock_client

        from app.api.agent.checklist_agent import normalize_categories
        result = await normalize_categories(
            ["안전복장 미착용인가?", "구명복 미착용인가?", "크레인 작업반경 내 무단출입인가?"]
        )

    assert len(result) == 2
    ppe = next(c for c in result if c["code"] == "PPE_MISSING")
    assert len(ppe["items"]) == 2
    assert "안전복장 미착용인가?" in ppe["items"]
    assert "구명복 미착용인가?" in ppe["items"]


@pytest.mark.asyncio
async def test_normalize_categories_empty_input():
    """빈 입력이면 LLM 호출 없이 빈 배열 반환."""
    from app.api.agent.checklist_agent import normalize_categories
    result = await normalize_categories([])
    assert result == []


@pytest.mark.asyncio
async def test_normalize_categories_fallback_on_empty_response():
    """LLM이 빈 응답 반환 시 GENERAL 카테고리 단일 반환."""
    mock_resp = MagicMock()
    mock_resp.choices[0].message.content = ""

    with patch("app.api.agent.checklist_agent._get_openai") as mock_get:
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_resp)
        mock_get.return_value = mock_client

        from app.api.agent.checklist_agent import normalize_categories
        items = ["항목1?", "항목2?"]
        result = await normalize_categories(items)

    assert len(result) == 1
    assert result[0]["code"] == "GENERAL"
    assert result[0]["items"] == items


@pytest.mark.asyncio
async def test_normalize_categories_missing_items_get_uncategorized():
    """LLM이 일부 항목 누락 시 UNCATEGORIZED로 자동 보완."""
    mock_resp = _make_mock_response([
        {"code": "PPE_MISSING", "label": "보호장비 미착용", "items": ["항목1?"]},
        # 항목2? 누락
    ])

    with patch("app.api.agent.checklist_agent._get_openai") as mock_get:
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_resp)
        mock_get.return_value = mock_client

        from app.api.agent.checklist_agent import normalize_categories
        result = await normalize_categories(["항목1?", "항목2?"])

    codes = [c["code"] for c in result]
    assert "UNCATEGORIZED" in codes
    uncategorized = next(c for c in result if c["code"] == "UNCATEGORIZED")
    assert "항목2?" in uncategorized["items"]


@pytest.mark.asyncio
async def test_normalize_categories_fallback_on_api_error():
    """API 오류 시 GENERAL 카테고리로 fallback, 예외 전파 없음."""
    with patch("app.api.agent.checklist_agent._get_openai") as mock_get:
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(side_effect=Exception("API 오류"))
        mock_get.return_value = mock_client

        from app.api.agent.checklist_agent import normalize_categories
        items = ["항목1?"]
        result = await normalize_categories(items)

    assert len(result) == 1
    assert result[0]["code"] == "GENERAL"
    assert result[0]["items"] == items
