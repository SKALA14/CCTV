import logging
import os
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

_SYSTEM = (
    "당신은 CCTV 보안 이벤트 검색 최적화 도우미입니다. "
    "주어진 이벤트 정보를 바탕으로 한국어로 풍부하게 묘사하세요. "
    "동의어와 관련 용어를 자연스럽게 포함하고, 100자 이내로 작성하세요. "
    "예: 낙상 사고 발생. 작업자가 바닥에 넘어져 쓰러짐. 추락, fall, 넘어짐 포함."
)

# Lazy-initialized to avoid requiring API key at import time during tests
_openai = None


async def describe_for_embedding(event_type: str, danger_level: str, description: str) -> str:
    user_content = f"event_type={event_type}, danger_level={danger_level}, description={description}"
    try:
        # Use _get_openai() at runtime; tests will patch _openai directly
        global _openai
        if _openai is None:
            _openai = AsyncOpenAI()

        resp = await _openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": user_content},
            ],
            temperature=0.1,
            max_tokens=150,
        )
        return (resp.choices[0].message.content or "").strip() or f"{event_type} {danger_level} {description}".strip()
    except Exception:
        logger.warning("embed_describer 실패, 원본 텍스트 사용: event_type=%s", event_type, exc_info=True)
        return f"{event_type} {danger_level} {description}".strip()
