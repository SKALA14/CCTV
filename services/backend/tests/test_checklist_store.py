from app.api.checklist_store import (
    flatten_categories, format_numbered, item_to_code, categories_map, items_map,
)


def test_flatten_categories_preserves_order():
    cats = [
        {"code": "A", "label": "에이", "items": ["q1?", "q2?"]},
        {"code": "B", "label": "비", "items": ["q3?"]},
    ]
    assert flatten_categories(cats) == ["q1?", "q2?", "q3?"]


def test_format_numbered_matches_legacy_format():
    assert format_numbered(["q1?", "q2?"]) == "1. q1?\n2. q2?"
    assert format_numbered([]) == ""
    assert "[" not in format_numbered(["q1?"])  # 코드 태그 없음


def test_item_to_code_maps_each_item():
    cats = [{"code": "A", "label": "에이", "items": ["q1?", "q2?"]}]
    assert item_to_code(cats) == {"q1?": "A", "q2?": "A"}


def test_categories_map_is_1based_index_to_code():
    cats = [
        {"code": "A", "label": "에이", "items": ["q1?"]},
        {"code": "B", "label": "비", "items": ["q2?"]},
    ]
    assert categories_map(cats) == {"1": "A", "2": "B"}
    assert categories_map([]) == {}


def test_items_map_uses_lookup_default_general():
    lookup = {"q1?": "A"}
    assert items_map(["q1?", "q99?"], lookup) == {"1": "A", "2": "GENERAL"}


import json
import pytest
from app.api.checklist_store import persist


class _FakeRedis:
    """hset/delete만 기록하는 인메모리 스텁."""
    def __init__(self):
        self.store: dict[str, dict] = {}

    async def delete(self, key):
        self.store.pop(key, None)

    async def hset(self, key, mapping=None):
        self.store.setdefault(key, {}).update(mapping or {})

    async def hgetall(self, key):
        return dict(self.store.get(key, {}))


def _sample_data():
    return {
        "static": {"categories": [{"code": "FIRE", "label": "소방", "items": ["소화기 가렸나?"]}]},
        "dynamic": {"categories": [{"code": "FALL", "label": "낙상", "items": ["쓰러졌나?"]}]},
        "zones": [{"zone": "정문 A", "static": ["소화기 가렸나?"], "dynamic": []}],
    }


@pytest.mark.asyncio
async def test_persist_writes_json_and_derived_md(tmp_path):
    redis = _FakeRedis()
    await persist(tmp_path, redis, "site1", _sample_data())

    saved = json.loads((tmp_path / "checklist.json").read_text(encoding="utf-8"))
    assert saved["static"]["categories"][0]["code"] == "FIRE"

    assert (tmp_path / "static_checklist.md").read_text(encoding="utf-8") == "1. 소화기 가렸나?"
    assert (tmp_path / "dynamic_checklist.md").read_text(encoding="utf-8") == "1. 쓰러졌나?"

    assert redis.store["checklist:site1:static:categories"] == {"1": "FIRE"}
    assert redis.store["checklist:site1:dynamic:categories"] == {"1": "FALL"}

    assert (tmp_path / "zone_정문_A_static.md").read_text(encoding="utf-8") == "1. 소화기 가렸나?"
    assert redis.store["checklist:site1:zone_정문_A:static:categories"] == {"1": "FIRE"}


@pytest.mark.asyncio
async def test_persist_empty_section_clears_redis(tmp_path):
    redis = _FakeRedis()
    redis.store["checklist:site1:static:categories"] = {"1": "OLD"}
    data = {"static": {"categories": []}, "dynamic": {"categories": []}, "zones": []}
    await persist(tmp_path, redis, "site1", data)
    assert "checklist:site1:static:categories" not in redis.store
    assert (tmp_path / "static_checklist.md").read_text(encoding="utf-8") == ""


from app.api.checklist_store import load_structured, parse_numbered


def test_parse_numbered_extracts_items():
    assert parse_numbered("1. q1?\n2. q2?") == ["q1?", "q2?"]
    assert parse_numbered("") == []
    # 항목에 '. '가 포함돼도 첫 번호만 제거
    assert parse_numbered("1. a. b?") == ["a. b?"]


@pytest.mark.asyncio
async def test_load_structured_reads_existing_json(tmp_path):
    redis = _FakeRedis()
    await persist(tmp_path, redis, "s1", _sample_data())
    loaded = await load_structured(tmp_path, redis, "s1")
    assert loaded["static"]["categories"][0]["items"] == ["소화기 가렸나?"]


@pytest.mark.asyncio
async def test_load_structured_reconstructs_from_legacy(tmp_path):
    # checklist.json 없이 레거시 .md + redis 맵 + zones.json만 존재
    redis = _FakeRedis()
    (tmp_path / "static_checklist.md").write_text("1. 소화기 가렸나?\n2. 통로 막혔나?", encoding="utf-8")
    (tmp_path / "dynamic_checklist.md").write_text("1. 쓰러졌나?", encoding="utf-8")
    redis.store["checklist:s1:static:categories"] = {"1": "FIRE", "2": "FIRE"}
    redis.store["checklist:s1:dynamic:categories"] = {"1": "FALL"}
    (tmp_path / "zones.json").write_text(
        json.dumps([{"zone": "정문 A", "description": ""}], ensure_ascii=False), encoding="utf-8"
    )
    (tmp_path / "zone_정문_A_static.md").write_text("1. 소화기 가렸나?", encoding="utf-8")

    data = await load_structured(tmp_path, redis, "s1")

    fire = data["static"]["categories"][0]
    assert fire["code"] == "FIRE"
    assert fire["label"] == "FIRE"
    assert fire["items"] == ["소화기 가렸나?", "통로 막혔나?"]
    assert data["dynamic"]["categories"][0]["items"] == ["쓰러졌나?"]
    assert data["zones"][0]["zone"] == "정문 A"
    assert data["zones"][0]["static"] == ["소화기 가렸나?"]


from app.api.checklist_store import apply_removes, apply_adds, apply_zone_assignments


def _merge_base():
    return {
        "static": {"categories": [
            {"code": "FIRE", "label": "소방", "items": ["소화기 가렸나?", "통로 막혔나?"]},
        ]},
        "dynamic": {"categories": [{"code": "FALL", "label": "낙상", "items": ["쓰러졌나?"]}]},
        "zones": [{"zone": "정문", "static": ["소화기 가렸나?"], "dynamic": []}],
    }


def test_apply_removes_strips_from_categories_and_zones():
    data = _merge_base()
    apply_removes(data, static_remove=["소화기 가렸나?"], dynamic_remove=[])
    assert data["static"]["categories"][0]["items"] == ["통로 막혔나?"]
    assert data["zones"][0]["static"] == []   # 전 구역에서도 제거


def test_apply_removes_drops_empty_category():
    data = _merge_base()
    apply_removes(data, static_remove=["소화기 가렸나?", "통로 막혔나?"], dynamic_remove=[])
    assert data["static"]["categories"] == []


def test_apply_adds_appends_to_general():
    data = _merge_base()
    apply_adds(data, static_add=["새 항목?"], dynamic_add=[])
    gen = next(c for c in data["static"]["categories"] if c["code"] == "GENERAL")
    assert gen["items"] == ["새 항목?"]
    assert gen["label"] == "일반"


def test_apply_adds_is_idempotent():
    data = _merge_base()
    apply_adds(data, static_add=["통로 막혔나?"], dynamic_add=[])  # 이미 존재
    flat = [i for c in data["static"]["categories"] for i in c["items"]]
    assert flat.count("통로 막혔나?") == 1


def test_apply_zone_assignments_appends_only_new():
    data = _merge_base()
    apply_zone_assignments(data, [{"zone": "정문", "static": ["새 항목?"], "dynamic": []}])
    assert data["zones"][0]["static"] == ["소화기 가렸나?", "새 항목?"]
