#!/usr/bin/env python3
"""
체크리스트 Agent 단독 테스트.
백엔드/Redis 없이 OpenAI API 키만으로 실행.

Usage:
    OPENAI_API_KEY=sk-... python scripts/test_checklist.py path/to/manual.pdf
"""

import asyncio
import os
import sys
from pathlib import Path

# infra/.env에서 환경변수 로드 (이미 설정된 값은 덮어쓰지 않음)
_env_file = Path(__file__).resolve().parent.parent / "infra" / ".env"
if _env_file.exists():
    for _line in _env_file.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _, _v = _line.partition("=")
            os.environ.setdefault(_k.strip(), _v.strip())

# services/backend를 import 경로에 추가
BACKEND = Path(__file__).resolve().parent.parent / "services" / "backend"
sys.path.insert(0, str(BACKEND))

try:
    import pdfplumber as _pdfplumber  # noqa: F401 — 설치 확인용
    del _pdfplumber
except ImportError:
    print("필요 패키지: pip install pdfplumber openai pydantic-settings")
    sys.exit(1)

import app.api.agent.checklist_agent as _agent

_agent._MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o")
from app.api.agent.checklist_agent import analyze_pdf
from app.api.agent.pdf_parser import extract_text_from_pdf


# Redis 세션 저장을 건너뜀 (Redis 불필요)
async def _noop_save(*_):
    pass

_agent._save_session = _noop_save


def _render_md(categories: list) -> str:
    sections = []
    for cat in categories:
        lines = [f"## {cat['category']}"] + [f"- {item}" for item in cat.get("items", [])]
        sections.append("\n".join(lines))
    return "\n\n".join(sections)


def save_results(static_cats: list, dynamic_cats: list) -> None:
    out_dir = Path(__file__).resolve().parent.parent / "sample" / "prompt"
    out_dir.mkdir(parents=True, exist_ok=True)

    static_path = out_dir / "static_checklist.md"
    dynamic_path = out_dir / "dynamic_checklist.md"

    static_path.write_text(_render_md(static_cats), encoding="utf-8")
    dynamic_path.write_text(_render_md(dynamic_cats), encoding="utf-8")

    print(f"저장 완료: {static_path}")
    print(f"저장 완료: {dynamic_path}")


async def main() -> None:
    if len(sys.argv) < 2:
        print(f"Usage: python {sys.argv[0]} <path/to/manual.pdf>")
        sys.exit(1)

    repo_root = Path(__file__).resolve().parent.parent
    pdf_path = repo_root / "sample" / "manual" / sys.argv[1]
    print(f"파일: {pdf_path}")

    print("PDF 텍스트 추출 중...")
    try:
        content = pdf_path.read_bytes()
        pdf_text = extract_text_from_pdf(content)
    except FileNotFoundError:
        print(f"오류: 파일을 찾을 수 없습니다 — {pdf_path}")
        sys.exit(1)
    except ValueError as e:
        print(f"오류: {e}")
        sys.exit(1)
    print(f"  → {len(pdf_text)}자 추출됨\n")

    print("체크리스트 분석 중...")
    result, _ = await analyze_pdf(pdf_text)

    static_cats = result.get("static", [])
    dynamic_cats = result.get("dynamic", [])

    def _print_track(label: str, categories: list) -> None:
        total = sum(len(c.get("items", [])) for c in categories)
        print("\n" + "=" * 60)
        print(f"[{label}] ({total}개)")
        print("=" * 60)
        for cat in categories:
            print(f"\n[{cat.get('category', '')}]")
            for item in cat.get("items", []):
                print(f"  - {item}")

    _print_track("STATIC — 주기 스냅샷 VLM 판단", static_cats)
    _print_track("DYNAMIC — 움직임 감지 후 VLM 판단", dynamic_cats)

    print()
    save_results(static_cats, dynamic_cats)


if __name__ == "__main__":
    asyncio.run(main())
