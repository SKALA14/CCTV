#!/usr/bin/env python3
"""
Zone subset 분석 테스트.
analyze_pdf → subset_by_zones 전체 흐름 검증.

Usage:
    python scripts/test_zones.py <pdf이름>              # 기본 zones.csv 사용
    python scripts/test_zones.py <pdf이름> <csv이름>    # sample/zones/<csv이름> 사용

pdf: sample/manual/ 아래 파일명
csv: sample/zones/ 아래 파일명 (없으면 기본 구역 3개로 자동 생성)
"""

import asyncio
import os
import sys
from pathlib import Path

_env_file = Path(__file__).resolve().parent.parent / "infra" / ".env"
if _env_file.exists():
    for _line in _env_file.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _, _v = _line.partition("=")
            os.environ.setdefault(_k.strip(), _v.strip())

BACKEND = Path(__file__).resolve().parent.parent / "services" / "backend"
sys.path.insert(0, str(BACKEND))

import app.api.agent.checklist_agent as _agent

_agent._MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o")

from app.api.agent.checklist_agent import analyze_pdf, subset_by_zones
from app.api.agent.pdf_parser import extract_text_from_pdf

async def _noop_save(*_):
    pass

_agent._save_session = _noop_save

DEFAULT_ZONES = [
    {"zone": "크레인 작업구역", "description": "천장 크레인으로 중량물을 이동시키는 구역"},
    {"zone": "용접 작업구역", "description": "금속 용접 및 절단 작업이 이루어지는 구역"},
    {"zone": "자재 적치구역", "description": "원자재 및 완성품을 보관하는 창고 구역"},
]


def _load_csv(path: Path) -> list[dict]:
    import csv
    rows = []
    with open(path, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            zone = row.get("zone", "").strip()
            if zone:
                rows.append({"zone": zone, "description": row.get("description", "").strip()})
    return rows


def _print_section(title: str, items: list[str]) -> None:
    if not items:
        return
    print(f"  [{title}]")
    for item in items:
        print(f"    · {item}")


async def main() -> None:
    repo_root = Path(__file__).resolve().parent.parent

    if len(sys.argv) < 2:
        print(f"Usage: python {sys.argv[0]} <pdf이름> [csv이름]")
        sys.exit(1)

    pdf_path = repo_root / "sample" / "manual" / sys.argv[1]
    if not pdf_path.exists():
        print(f"오류: {pdf_path} 파일 없음")
        sys.exit(1)

    zones = DEFAULT_ZONES
    if len(sys.argv) >= 3:
        csv_path = repo_root / "sample" / "zones" / sys.argv[2]
        if not csv_path.exists():
            print(f"오류: {csv_path} 파일 없음")
            sys.exit(1)
        zones = _load_csv(csv_path)
        print(f"구역 파일: {csv_path} ({len(zones)}개 구역)")
    else:
        print(f"구역: 기본값 {len(zones)}개 사용 (sample/zones/<파일>.csv 로 지정 가능)")

    print(f"PDF: {pdf_path}\n")

    print("1단계 — 글로벌 체크리스트 생성 중...")
    content = pdf_path.read_bytes()
    pdf_text = extract_text_from_pdf(content)
    print(f"  텍스트 {len(pdf_text)}자 추출\n")

    result, session_id = await analyze_pdf(pdf_text)

    def _flat(cats):
        return [item for cat in cats for item in (cat.get("items", []) if isinstance(cat, dict) else [])]

    static_items = _flat(result.get("static", []))
    dynamic_items = _flat(result.get("dynamic", []))

    print(f"글로벌 체크리스트 (static {len(static_items)}개 / dynamic {len(dynamic_items)}개)")
    print("=" * 60)
    _print_section("STATIC", static_items)
    _print_section("DYNAMIC", dynamic_items)
    print()

    print(f"2단계 — 구역별 subset 생성 중... ({len(zones)}개 구역)")
    zone_results = await subset_by_zones(result, zones)
    print()

    print("구역별 체크리스트")
    print("=" * 60)
    for z in zone_results:
        name = z.get("zone", "")
        s = z.get("static", [])
        d = z.get("dynamic", [])
        print(f"\n[ {name} ]  (static {len(s)}개 / dynamic {len(d)}개)")
        _print_section("STATIC", s)
        _print_section("DYNAMIC", d)

    print()
    missing = [z["zone"] for z in zones if not any(r.get("zone") == z["zone"] for r in zone_results)]
    if missing:
        print(f"⚠ 결과 없는 구역: {', '.join(missing)}")


if __name__ == "__main__":
    asyncio.run(main())
