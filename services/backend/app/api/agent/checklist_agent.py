import json
import logging
import uuid

import redis.asyncio as aioredis
from openai import AsyncOpenAI

from app.config import config

logger = logging.getLogger(__name__)
_openai: AsyncOpenAI | None = None

_SESSION_TTL = 3600
_MODEL = "gpt-4o"


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


async def analyze_pdf(pdf_text: str, session_id: str | None = None) -> tuple[dict, str]:
    """PDF 텍스트를 3단계 에이전트로 분석해 {static, dynamic} 체크리스트와 session_id 반환."""
    if session_id is None:
        session_id = str(uuid.uuid4())

    # Step 1: 안전 항목 전체 추출
    s1_system = (
        "산업 안전 전문가. PDF 텍스트에서 위험 요인과 안전 점검 항목을 빠짐없이 추출하라. "
        '{"items": ["항목1", "항목2", ...]} 형태 JSON으로 출력하라.'
    )
    s1_messages = [
        {"role": "system", "content": s1_system},
        {"role": "user", "content": pdf_text},
    ]
    resp1 = await _get_openai().chat.completions.create(
        model=_MODEL,
        messages=s1_messages,
        response_format={"type": "json_object"},
    )
    raw1 = resp1.choices[0].message.content or ""
    if not raw1:
        raise ValueError("LLM이 빈 응답을 반환했습니다.")
    parsed1 = json.loads(raw1)
    if isinstance(parsed1, dict):
        items = parsed1.get("items") or next((v for v in parsed1.values() if isinstance(v, list)), [])
    else:
        items = []
    if not isinstance(items, list):
        items = []

    # Step 2: static / dynamic / unverifiable 분류
    s2_system = (
        "아래 안전 점검 항목을 CCTV 영상 분석 관점에서 세 가지로 분류하라.\n\n"
        "[분류 기준]\n"
        "static: 사람 없이 물체·공간의 물리적 상태만으로 판단 가능. 30분 간격 스냅샷 1장으로 충분.\n"
        "  예) 통로 장애물 방치, 소화기 위치 차단, 적재물 높이 초과, 안전난간 미설치\n\n"
        "dynamic: 사람의 존재·행동·이벤트 감지가 필요. 움직임 감지 후 VLM이 판단.\n"
        "  예) PPE(안전모·안전화·장갑) 미착용, 낙상, 지게차-사람 근접, 화재·연기, 신호 미준수\n\n"
        "unverifiable: CCTV 해상도·거리·각도 특성상 판단 불가. 표시판 글씨 확인, 볼트 체결 여부,\n"
        "  접지 상태, 문서·서류 확인, 소음·진동 등 시각으로 감지 불가능한 항목.\n\n"
        "규칙:\n"
        "- PPE 착용 여부는 반드시 dynamic으로 분류 (사람이 있어야 판단 가능)\n"
        "- '표시를 통해 확인', '라벨 확인', '서류 확인' 등은 unverifiable\n"
        "- 판단이 애매하면 dynamic 우선\n"
        "- unverifiable은 최종 결과에서 제외되므로 엄격하게 적용\n\n"
        '{"static": [...], "dynamic": [...], "unverifiable": [...]} 형태 JSON으로 출력하라.'
    )
    s2_messages = [
        {"role": "system", "content": s2_system},
        {"role": "user", "content": json.dumps(items, ensure_ascii=False)},
    ]
    resp2 = await _get_openai().chat.completions.create(
        model=_MODEL,
        messages=s2_messages,
        response_format={"type": "json_object"},
    )
    raw2 = resp2.choices[0].message.content or ""
    if not raw2:
        raise ValueError("LLM이 빈 응답을 반환했습니다.")
    classified: dict = json.loads(raw2)
    verifiable = {
        "static": classified.get("static", []),
        "dynamic": classified.get("dynamic", []),
    }

    # Step 3: VLM 판단 가능한 구체적 문장으로 포맷 변환
    s3_system = (
        "각 항목을 CCTV VLM이 화면에서 직접 판단할 수 있는 구체적 문장으로 변환하라.\n\n"
        "[변환 규칙]\n"
        "- 주어는 항상 화면에서 관찰 가능한 대상 (작업자, 장비, 공간, 물체)\n"
        "- 동사는 시각적으로 확인 가능한 행위·상태 (착용, 방치, 접근, 쓰러짐 등)\n"
        "- '확인하라', '점검하라' 등 지시형 표현 금지 → 관찰 서술형으로 작성\n"
        "- 추상·절차·문서 기반 표현 금지 (예: '절차에 따라', '기준에 맞게')\n"
        "- static 항목: 사람 없이도 판단 가능한 물체·공간 상태로만 기술\n"
        "- dynamic 항목: 사람의 행동·이벤트가 드러나는 서술로 기술\n\n"
        "[예시]\n"
        "before: '모든 작업자가 헬멧, 장갑, 안전화 등 개인보호구를 착용하고 있는지 확인'\n"
        "after(dynamic): '작업자가 안전모·안전화·장갑을 착용하지 않은 상태로 작업 구역에 있음'\n\n"
        "before: '안전 통로에 장애물이 방치됨'\n"
        "after(static): '지정된 보행 통로 위에 자재·장비·물체가 놓여 통행이 차단된 상태'\n\n"
        '{"static": [...], "dynamic": [...]} 형태 JSON으로 출력하라.'
    )
    s3_messages = [
        {"role": "system", "content": s3_system},
        {"role": "user", "content": json.dumps(verifiable, ensure_ascii=False)},
    ]
    resp3 = await _get_openai().chat.completions.create(
        model=_MODEL,
        messages=s3_messages,
        response_format={"type": "json_object"},
    )
    raw3 = resp3.choices[0].message.content or ""
    if not raw3:
        raise ValueError("LLM이 빈 응답을 반환했습니다.")
    result: dict = json.loads(raw3)

    history = (
        s1_messages
        + [{"role": "assistant", "content": raw1}]
        + [s2_messages[1]]
        + [{"role": "assistant", "content": raw2}]
        + [s3_messages[1]]
        + [{"role": "assistant", "content": raw3}]
    )
    await _save_session(session_id, history)

    return result, session_id


async def refine_checklist(session_id: str, feedback: str) -> dict:
    """피드백을 반영해 체크리스트 재생성. {static, dynamic} 반환."""
    messages = await _load_session(session_id)
    if not messages:
        raise ValueError(f"세션을 찾을 수 없습니다: {session_id}")
    if messages[0].get("role") != "system":
        messages = [
            {
                "role": "system",
                "content": (
                    "산업 안전 전문가. 기존 static/dynamic 체크리스트를 피드백에 따라 수정하라.\n"
                    'JSON으로 출력하라: {"static": [...], "dynamic": [...]}'
                ),
            }
        ] + messages
    messages.append({
        "role": "user",
        "content": (
            f"피드백: {feedback}\n"
            "위 피드백을 반영하여 static/dynamic 체크리스트를 수정하라.\n"
            '{"static": [...], "dynamic": [...]} 형태 JSON으로 출력하라.'
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
