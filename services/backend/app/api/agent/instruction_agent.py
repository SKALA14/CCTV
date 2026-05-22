import json
import logging
from pathlib import Path

from openai import AsyncOpenAI

from app.config import config

logger = logging.getLogger(__name__)
_openai: AsyncOpenAI | None = None

_MODEL = "gpt-4o"


def _get_openai() -> AsyncOpenAI:
    global _openai
    if _openai is None:
        _openai = AsyncOpenAI()
    return _openai


def _load_global_checklist() -> str:
    """static/dynamic 글로벌 체크리스트를 읽어 단일 문자열로 반환. 파일이 없으면 빈 문자열."""
    prompts_dir = Path(config.PROMPTS_DIR)
    static_path = prompts_dir / "static_checklist.md"
    dynamic_path = prompts_dir / "dynamic_checklist.md"

    static_text = static_path.read_text(encoding="utf-8") if static_path.exists() else ""
    dynamic_text = dynamic_path.read_text(encoding="utf-8") if dynamic_path.exists() else ""

    return f"[Static 체크리스트]\n{static_text}\n\n[Dynamic 체크리스트]\n{dynamic_text}".strip()


async def analyze_instruction(user_input: str) -> dict:
    """채널별 자유 텍스트를 글로벌 체크리스트와 비교해 static/dynamic 분류 후 VLM용 문장으로 변환."""
    global_checklist = _load_global_checklist()
    messages = [
        {
            "role": "system",
            "content": (
                f"전역 체크리스트:\n{global_checklist}\n\n"
                "위 항목과 중복되지 않는 항목만 추출하라.\n"
                "입력 텍스트를 static/dynamic으로 분류하고 VLM이 CCTV 화면에서 직접 판단 가능한 구체적 문장으로 변환하라.\n"
                '추상적 표현 금지. JSON으로 출력하라: {"static": [...], "dynamic": [...]}'
            ),
        },
        {"role": "user", "content": user_input},
    ]
    resp = await _get_openai().chat.completions.create(
        model=_MODEL,
        messages=messages,
        response_format={"type": "json_object"},
    )
    raw = resp.choices[0].message.content or ""
    if not raw:
        raise ValueError("LLM이 빈 응답을 반환했습니다.")
    return json.loads(raw)
