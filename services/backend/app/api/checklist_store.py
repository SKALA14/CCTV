"""체크리스트 구조화 JSON ↔ 파생물(.json/Redis) 변환·저장·로드·병합.

순수 함수 + Redis를 인자로 주입받는 async 함수로 구성해 단위테스트가 쉽다.
구조화 JSON 형태:
  {"static": {"categories": [{"code","label","severity","items":[...]}]},
   "dynamic": {"categories": [...]},
   "zones": [{"zone","static":[...],"dynamic":[...]}]}
"""

from __future__ import annotations

import json
import re
from pathlib import Path

_NUM_PREFIX = re.compile(r"^\s*\d+\.\s+")
_VALID_SEVERITIES = frozenset({"critical", "high", "low", "none"})


def flatten_categories(categories: list[dict]) -> list[str]:
    """카테고리 리스트에서 항목 문자열을 순서대로 평탄화."""
    out: list[str] = []
    for cat in categories:
        out.extend(cat.get("items", []))
    return out


def format_numbered(items: list[str]) -> str:
    """번호 형식 텍스트. 레거시 .md 역구성용."""
    if not items:
        return ""
    return "\n".join(f"{i + 1}. {item}" for i, item in enumerate(items))


def format_checklist_json(categories: list[dict]) -> str:
    """체크리스트를 {id, text, severity} JSON Lines 형태로 포맷. 인퍼런스 프롬프트에 주입."""
    lines = []
    idx = 1
    for cat in categories:
        raw = cat.get("severity", "low")
        sev = raw if raw in _VALID_SEVERITIES else "low"
        for item in cat.get("items", []):
            lines.append(json.dumps({"id": idx, "text": item, "severity": sev}, ensure_ascii=False))
            idx += 1
    return "\n".join(lines)


def format_checklist_json_for_zone(items: list[str], sev_lookup: dict[str, str]) -> str:
    """구역 항목 리스트를 {id, text, severity} JSON Lines 형태로 포맷."""
    lines = []
    for idx, item in enumerate(items, 1):
        sev = sev_lookup.get(item, "low")
        lines.append(json.dumps({"id": idx, "text": item, "severity": sev}, ensure_ascii=False))
    return "\n".join(lines)


def item_to_code(categories: list[dict]) -> dict[str, str]:
    """항목 문자열 → 카테고리 코드 lookup."""
    lookup: dict[str, str] = {}
    for cat in categories:
        code = cat.get("code", "GENERAL")
        for item in cat.get("items", []):
            lookup[item] = code
    return lookup


def item_to_severity(categories: list[dict]) -> dict[str, str]:
    """항목 문자열 → severity lookup. 유효하지 않은 값은 'low'로 고정."""
    lookup: dict[str, str] = {}
    for cat in categories:
        raw = cat.get("severity", "low")
        sev = raw if raw in _VALID_SEVERITIES else "low"
        for item in cat.get("items", []):
            lookup[item] = sev
    return lookup


def categories_map(categories: list[dict]) -> dict[str, str]:
    """1-based 인덱스(str) → 코드. Redis HSET용. 빈 입력이면 {}."""
    items = flatten_categories(categories)
    if not items:
        return {}
    lookup = item_to_code(categories)
    return {str(i + 1): lookup.get(item, "GENERAL") for i, item in enumerate(items)}


def severities_map(categories: list[dict]) -> dict[str, str]:
    """1-based 인덱스(str) → severity. Redis HSET용. 빈 입력이면 {}."""
    items = flatten_categories(categories)
    if not items:
        return {}
    lookup = item_to_severity(categories)
    return {str(i + 1): lookup.get(item, "low") for i, item in enumerate(items)}


def items_map(items: list[str], lookup: dict[str, str]) -> dict[str, str]:
    """구역 항목 리스트 → 1-based 인덱스(str)→코드. lookup에 없으면 GENERAL."""
    if not items:
        return {}
    return {str(i + 1): lookup.get(item, "GENERAL") for i, item in enumerate(items)}


def severity_map_for_items(items: list[str], lookup: dict[str, str]) -> dict[str, str]:
    """구역 항목 리스트 → 1-based 인덱스(str)→severity. lookup에 없으면 'low'."""
    if not items:
        return {}
    return {str(i + 1): lookup.get(item, "low") for i, item in enumerate(items)}


async def _write_map(redis, key: str, mapping: dict[str, str]) -> None:
    await redis.delete(key)
    if mapping:
        await redis.hset(key, mapping=mapping)


async def persist(site_dir: Path, redis, sid: str, data: dict) -> None:
    """구조화 JSON을 단일 원본으로 저장하고 .md/Redis 파생물을 재생성.

    site_dir: 현장 디렉토리(Path). redis: aioredis 호환(주입). sid: 현장 id 문자열.
    """
    site_dir = Path(site_dir)
    site_dir.mkdir(parents=True, exist_ok=True)

    (site_dir / "checklist.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    s_cats = data.get("static", {}).get("categories", [])
    d_cats = data.get("dynamic", {}).get("categories", [])

    (site_dir / "static_checklist.json").write_text(format_checklist_json(s_cats), encoding="utf-8")
    (site_dir / "dynamic_checklist.json").write_text(format_checklist_json(d_cats), encoding="utf-8")
    await _write_map(redis, f"checklist:{sid}:static:categories", categories_map(s_cats))
    await _write_map(redis, f"checklist:{sid}:dynamic:categories", categories_map(d_cats))

    s_lookup = item_to_code(s_cats)
    d_lookup = item_to_code(d_cats)
    s_sev_lookup = item_to_severity(s_cats)
    d_sev_lookup = item_to_severity(d_cats)
    for zone in data.get("zones", []):
        safe = zone["zone"].replace(" ", "_")
        zs = zone.get("static", [])
        zd = zone.get("dynamic", [])
        (site_dir / f"zone_{safe}_static.json").write_text(format_checklist_json_for_zone(zs, s_sev_lookup), encoding="utf-8")
        (site_dir / f"zone_{safe}_dynamic.json").write_text(format_checklist_json_for_zone(zd, d_sev_lookup), encoding="utf-8")
        await _write_map(redis, f"checklist:{sid}:zone_{safe}:static:categories", items_map(zs, s_lookup))
        await _write_map(redis, f"checklist:{sid}:zone_{safe}:dynamic:categories", items_map(zd, d_lookup))


def parse_numbered(text: str) -> list[str]:
    """번호 형식 .md 텍스트에서 항목 문자열 추출."""
    items: list[str] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        items.append(_NUM_PREFIX.sub("", line, count=1))
    return items


def _group_by_code(items: list[str], idx_to_code: dict[str, str]) -> list[dict]:
    """항목+(index→code) 맵으로 카테고리 리스트 재구성. 등장 순서 유지, label=code."""
    if not items:
        return []
    grouped: dict[str, dict] = {}
    order: list[str] = []
    for i, item in enumerate(items):
        code = idx_to_code.get(str(i + 1), "GENERAL")
        if code not in grouped:
            grouped[code] = {"code": code, "label": code, "items": []}
            order.append(code)
        grouped[code]["items"].append(item)
    return [grouped[c] for c in order]


async def reconstruct_from_legacy(site_dir: Path, redis, sid: str) -> dict:
    """checklist.json 없는 기존 현장을 .md+Redis+zones.json에서 역구성."""
    site_dir = Path(site_dir)

    def _section(md_name: str, idx_map: dict) -> dict:
        path = site_dir / md_name
        items = parse_numbered(path.read_text(encoding="utf-8")) if path.exists() else []
        return {"categories": _group_by_code(items, idx_map)}

    s_map = await redis.hgetall(f"checklist:{sid}:static:categories")
    d_map = await redis.hgetall(f"checklist:{sid}:dynamic:categories")
    data = {
        "static": _section("static_checklist.md", s_map),
        "dynamic": _section("dynamic_checklist.md", d_map),
        "zones": [],
    }

    zones_path = site_dir / "zones.json"
    if zones_path.exists():
        try:
            raw_zones = json.loads(zones_path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            raw_zones = []
        for z in raw_zones:
            name = z["zone"] if isinstance(z, dict) else z
            safe = name.replace(" ", "_")
            zs_path = site_dir / f"zone_{safe}_static.md"
            zd_path = site_dir / f"zone_{safe}_dynamic.md"
            data["zones"].append({
                "zone": name,
                "static": parse_numbered(zs_path.read_text(encoding="utf-8")) if zs_path.exists() else [],
                "dynamic": parse_numbered(zd_path.read_text(encoding="utf-8")) if zd_path.exists() else [],
            })
    return data


async def load_structured(site_dir: Path, redis, sid: str) -> dict:
    """checklist.json 있으면 읽고, 없으면 레거시 역구성."""
    path = Path(site_dir) / "checklist.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return await reconstruct_from_legacy(site_dir, redis, sid)


def apply_removes(data: dict, static_remove: list[str], dynamic_remove: list[str]) -> None:
    """수락된 삭제 항목을 공통 카테고리 + 모든 구역에서 제거(in-place). 빈 카테고리는 삭제."""
    for sec, removes in (("static", static_remove), ("dynamic", dynamic_remove)):
        rs = set(removes)
        if not rs:
            continue
        cats = data.get(sec, {}).get("categories", [])
        for cat in cats:
            cat["items"] = [it for it in cat.get("items", []) if it not in rs]
        data.setdefault(sec, {})["categories"] = [c for c in cats if c["items"]]
        for zone in data.get("zones", []):
            zone[sec] = [it for it in zone.get(sec, []) if it not in rs]


def apply_adds(data: dict, static_add: list[str], dynamic_add: list[str]) -> None:
    """수락된 추가 항목을 GENERAL 카테고리에 append(in-place, 중복 방지)."""
    for sec, adds in (("static", static_add), ("dynamic", dynamic_add)):
        if not adds:
            continue
        cats = data.setdefault(sec, {}).setdefault("categories", [])
        gen = next((c for c in cats if c.get("code") == "GENERAL"), None)
        if gen is None:
            gen = {"code": "GENERAL", "label": "일반", "items": []}
            cats.append(gen)
        existing = {it for c in cats for it in c.get("items", [])}
        for item in adds:
            if item not in existing:
                gen["items"].append(item)
                existing.add(item)


def apply_zone_assignments(data: dict, zone_subsets: list[dict]) -> None:
    """subset_by_zones 결과(새 항목의 구역 배치)를 기존 구역에 append(in-place, 중복 방지)."""
    by_name = {z["zone"]: z for z in data.get("zones", [])}
    for sub in zone_subsets:
        zone = by_name.get(sub.get("zone"))
        if zone is None:
            continue
        for sec in ("static", "dynamic"):
            existing = set(zone.get(sec, []))
            for item in sub.get(sec, []):
                if item not in existing:
                    zone.setdefault(sec, []).append(item)
                    existing.add(item)
