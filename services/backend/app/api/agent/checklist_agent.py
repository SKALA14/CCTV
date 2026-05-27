import json
import logging
import uuid

import redis.asyncio as aioredis
from openai import AsyncOpenAI

from app.config import config

logger = logging.getLogger(__name__)
_openai: AsyncOpenAI | None = None

_SESSION_TTL = 3600
_MODEL = config.OPENAI_MODEL


def _get_openai() -> AsyncOpenAI:
    global _openai
    if _openai is None:
        _openai = AsyncOpenAI()
    return _openai


_redis: aioredis.Redis | None = None


def _get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(config.REDIS_URL, decode_responses=True)
    return _redis


async def _load_session(session_id: str) -> list[dict]:
    r = _get_redis()
    raw = await r.get(f"checklist_session:{session_id}")
    return json.loads(raw) if raw else []


async def _save_session(session_id: str, messages: list[dict]) -> None:
    r = _get_redis()
    await r.setex(
        f"checklist_session:{session_id}",
        _SESSION_TTL,
        json.dumps(messages, ensure_ascii=False),
    )


_ANALYZE_SYSTEM = (
    "당신은 산업 안전 전문가입니다. 주어진 문서를 분석해 이 현장에 적용할 CCTV 안전 체크리스트를 작성하라.\n\n"
    "[추출 기준]\n"
    "- CCTV 화면에서 눈으로 직접 확인할 수 있는 물리적 상태·행동 위반만 포함\n"
    "- 반드시 문서에 명시된 내용만 추출하고, 문서에 없는 항목은 추가하지 마라\n"
    "- 유사·중복 항목은 하나로 통합하고, 가장 핵심적인 항목만 남겨라\n"
    "- static + dynamic 전체 항목 합산 10개 내외로 작성하라\n\n"
    "[제외 기준 — 아래 중 하나라도 해당하면 반드시 제외]\n"
    "- 소음·진동·냄새·온도 등 시각으로 감지 불가능한 항목\n"
    "- 속도·하중·무게·수치·농도 등 계측기로만 확인 가능한 항목\n"
    "- 안전검사·점검·자격증·인증·허가·계획서·사전조사 등 서류·절차로만 확인 가능한 항목\n"
    "- 담당자·책임자·지휘자 지정·배치 여부 (역할 판단 불가)\n"
    "- 장치·설비의 작동 여부 (직접 조작해야 확인 가능)\n"
    "- 볼트·접지·배선 등 근접 육안 검사가 필요한 항목\n\n"
    "[분류 기준]\n"
    "static: 사람 없이 물체·공간의 물리적 상태만으로 판단 가능. 30분 간격 스냅샷 1장으로 충분.\n"
    "dynamic: 사람의 존재·행동·이벤트 감지가 필요. 움직임 감지 후 VLM이 판단.\n\n"
    "[출력 규칙]\n"
    "- 관련 항목끼리 카테고리로 묶을 것 (도메인에 맞는 카테고리명 사용)\n"
    "- 각 항목은 '~인가?', '~있는가?', '~보이는가?' 형태의 질문으로 작성\n"
    "- 질문 주어는 화면에서 관찰 가능한 대상 (작업자, 장비, 공간, 물체)\n\n"
    '{"static": [{"category": "카테고리명", "items": ["질문1?", "질문2?"]}, ...], '
    '"dynamic": [{"category": "카테고리명", "items": ["질문1?", "질문2?"]}, ...]} '
    "형태 JSON으로 출력하라."
)


async def analyze_pdf(pdf_text: str, session_id: str | None = None) -> tuple[dict, str]:
    """PDF 텍스트를 단일 LLM 호출로 분석해 {static, dynamic} 체크리스트와 session_id 반환."""
    if session_id is None:
        session_id = str(uuid.uuid4())

    messages = [
        {"role": "system", "content": _ANALYZE_SYSTEM},
        {"role": "user", "content": pdf_text},
    ]
    resp = await _get_openai().chat.completions.create(
        model=_MODEL,
        messages=messages,
        response_format={"type": "json_object"},
    )
    raw = resp.choices[0].message.content or ""
    if not raw:
        raise ValueError("LLM이 빈 응답을 반환했습니다.")
    result: dict = json.loads(raw)

    await _save_session(session_id, messages + [{"role": "assistant", "content": raw}])
    return result, session_id


_ZONE_SUBSET_SYSTEM = (
    "전체 CCTV 안전 체크리스트와 구역 목록이 주어진다. "
    "각 구역의 작업 특성에 맞는 항목만 골라 subset을 구성하라.\n\n"
    "[규칙]\n"
    "- 구역 설명을 고려해 실제로 해당 구역에서 발생 가능한 위험과 관련된 항목만 선택\n"
    "- 전체 항목 중 일부를 그대로 가져올 것 (수정·추가 금지)\n"
    "- 구역당 static + dynamic 합산 5개 내외\n\n"
    '{"zones": [{"zone": "구역명", "static": ["...?"], "dynamic": ["...?"]}, ...]} 형태 JSON으로 출력하라.'
)


async def subset_by_zones(checklist: dict, zones: list[dict]) -> list[dict]:
    """전체 체크리스트에서 구역별 관련 항목 subset을 단일 LLM 호출로 생성."""
    def _flatten(categories: list) -> list[str]:
        return [item for cat in categories for item in (cat.get("items", []) if isinstance(cat, dict) else [cat])]

    flat = {
        "static": _flatten(checklist.get("static", [])),
        "dynamic": _flatten(checklist.get("dynamic", [])),
    }
    messages = [
        {"role": "system", "content": _ZONE_SUBSET_SYSTEM},
        {"role": "user", "content": json.dumps({"checklist": flat, "zones": zones}, ensure_ascii=False)},
    ]
    resp = await _get_openai().chat.completions.create(
        model=_MODEL,
        messages=messages,
        response_format={"type": "json_object"},
    )
    raw = resp.choices[0].message.content or ""
    if not raw:
        return []
    return json.loads(raw).get("zones", [])


async def refine_checklist(session_id: str, feedback: str) -> dict:
    """피드백을 반영해 체크리스트 재생성. {static, dynamic} 반환."""
    messages = await _load_session(session_id)
    if not messages:
        raise ValueError(f"세션을 찾을 수 없습니다: {session_id}")
    if messages[0].get("role") != "system":
        messages = [{"role": "system", "content": _ANALYZE_SYSTEM}] + messages
    messages.append({
        "role": "user",
        "content": (
            f"피드백: {feedback}\n\n"
            "위 피드백을 반영해 체크리스트를 수정하라. "
            "CCTV 판별 불가 항목 추가 금지, 문서에 없는 항목 추가 금지 원칙은 유지하라.\n"
            '{"static": [{"category": "...", "items": ["...?"]}], '
            '"dynamic": [{"category": "...", "items": ["...?"]}]} 형태 JSON으로 출력하라.'
        ),
    })
    resp = await _get_openai().chat.completions.create(
        model=_MODEL,
        messages=messages,
        response_format={"type": "json_object"},
    )
    raw = resp.choices[0].message.content or ""
    if not raw:
        raise ValueError("LLM이 빈 응답을 반환했습니다.")
    result: dict = json.loads(raw)
    messages.append({"role": "assistant", "content": raw})
    await _save_session(session_id, messages)
    return result
