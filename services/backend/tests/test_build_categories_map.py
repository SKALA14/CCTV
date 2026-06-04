# services/backend/tests/test_build_categories_map.py


def test_build_categories_map_basic():
    """항목 인덱스(1-based) → 카테고리 코드 매핑 생성."""
    from app.api.manuals import _build_categories_map

    class _Cat:
        def __init__(self, code, its):
            self.code = code
            self.items = its

    items = ["안전난간 설치됐는가?", "안전표지 부착됐는가?", "작업발판 설치됐는가?"]
    categories = [
        _Cat("SAFETY_BARRIERS", ["안전난간 설치됐는가?", "작업발판 설치됐는가?"]),
        _Cat("SAFETY_SIGNS", ["안전표지 부착됐는가?"]),
    ]
    result = _build_categories_map(items, categories)
    assert result == {"1": "SAFETY_BARRIERS", "2": "SAFETY_SIGNS", "3": "SAFETY_BARRIERS"}


def test_build_categories_map_without_categories_returns_empty():
    """categories 없으면 빈 dict 반환."""
    from app.api.manuals import _build_categories_map
    assert _build_categories_map(["항목1?"], []) == {}


def test_build_categories_map_unmapped_item_gets_general():
    """categories에 없는 항목은 'GENERAL' 코드 부여."""
    from app.api.manuals import _build_categories_map

    class _Cat:
        def __init__(self, code, its):
            self.code = code
            self.items = its

    items = ["항목1?", "매핑없음?"]
    categories = [_Cat("CODE_A", ["항목1?"])]
    result = _build_categories_map(items, categories)
    assert result == {"1": "CODE_A", "2": "GENERAL"}


def test_build_categories_map_empty_items():
    """빈 items면 빈 dict 반환."""
    from app.api.manuals import _build_categories_map
    assert _build_categories_map([], []) == {}


def test_build_categories_map_keys_are_strings():
    """인덱스 키가 문자열('1', '2', ...)이어야 함 — Redis HSET mapping 호환."""
    from app.api.manuals import _build_categories_map

    class _Cat:
        def __init__(self, code, its):
            self.code = code
            self.items = its

    result = _build_categories_map(["항목?"], [_Cat("CODE", ["항목?"])])
    assert all(isinstance(k, str) for k in result.keys())
