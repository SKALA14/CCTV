# services/backend/app/api/query_expander.py
"""검색어를 CCTV 보안 도메인 동의어로 확장하는 LLM 보조 모듈."""

import json
import logging
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

_SYSTEM = (
    "당신은 CCTV 보안 이벤트 검색 시스템의 쿼리 확장기입니다. "
    "사용자의 검색어를 CCTV 보안 도메인에서 의미적으로 같은 한국어/영어 표현으로 확장하세요. "
    "원본 포함 최대 5개를 JSON 배열로만 반환하세요. 다른 텍스트 없이 배열만 출력하세요. "
    '예: 입력 "불" → ["불", "화재", "연기", "화염", "불꽃"]'
)

# Lazy-initialized to avoid requiring API key at import time during tests
_openai = None


async def expand_query(q: str) -> list[str]:
    """검색어를 동의어 포함 최대 5개 변형으로 확장한다. 실패 시 원본만 담은 리스트 반환."""
    try:
        # Use lazy initialization; tests will patch _openai directly
        global _openai
        if _openai is None:
            _openai = AsyncOpenAI()

        resp = await _openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": q},
            ],
            temperature=0.1,
            max_tokens=100,
        )
        text = resp.choices[0].message.content or ""
        variants = json.loads(text.strip())
        if isinstance(variants, list) and all(isinstance(v, str) for v in variants) and variants:
            return variants[:5]
    except Exception:
        logger.warning("query expansion 실패, 원본 쿼리 사용: %s", q, exc_info=True)
    return [q]
