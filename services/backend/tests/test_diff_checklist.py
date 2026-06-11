import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _mock_resp(added, removed):
    resp = MagicMock()
    resp.choices[0].message.content = json.dumps(
        {"added": added, "removed_candidates": removed}, ensure_ascii=False
    )
    return resp


@pytest.mark.asyncio
async def test_diff_no_existing_returns_all_as_added():
    """기존 항목이 없으면 LLM 호출 없이 전부 added."""
    from app.api.agent.checklist_agent import diff_checklist
    result = await diff_checklist([], ["새1?", "새2?"])
    assert result == {"added": ["새1?", "새2?"], "removed_candidates": []}


@pytest.mark.asyncio
async def test_diff_no_new_returns_all_as_removed():
    """새 항목이 없으면 LLM 호출 없이 전부 removed_candidates."""
    from app.api.agent.checklist_agent import diff_checklist
    result = await diff_checklist(["기존1?"], [])
    assert result == {"added": [], "removed_candidates": ["기존1?"]}


@pytest.mark.asyncio
async def test_diff_semantic_split():
    """LLM이 added/removed_candidates로 분류한 결과를 그대로 반환."""
    mock = _mock_resp(added=["신규 항목?"], removed=["폐기된 항목?"])
    with patch("app.api.agent.checklist_agent._get_openai") as mock_get:
        client = MagicMock()
        client.chat.completions.create = AsyncMock(return_value=mock)
        mock_get.return_value = client
        from app.api.agent.checklist_agent import diff_checklist
        result = await diff_checklist(["폐기된 항목?", "유지 항목?"], ["유지 항목?", "신규 항목?"])
    assert result["added"] == ["신규 항목?"]
    assert result["removed_candidates"] == ["폐기된 항목?"]


@pytest.mark.asyncio
async def test_diff_empty_response_falls_back_to_set_diff():
    """LLM 빈 응답 시 단순 집합 차집합으로 fallback."""
    resp = MagicMock()
    resp.choices[0].message.content = ""
    with patch("app.api.agent.checklist_agent._get_openai") as mock_get:
        client = MagicMock()
        client.chat.completions.create = AsyncMock(return_value=resp)
        mock_get.return_value = client
        from app.api.agent.checklist_agent import diff_checklist
        result = await diff_checklist(["a?"], ["a?", "b?"])
    assert result["added"] == ["b?"]
    assert result["removed_candidates"] == []
