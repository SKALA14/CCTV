# services/backend/tests/test_format_checklist.py


def test_format_checklist_with_categories_returns_numbered():
    """categories 여부와 무관하게 항상 번호 형식으로 반환."""
    from app.api.manuals import _format_checklist

    class _Cat:
        def __init__(self, code, label, its):
            self.code = code
            self.label = label
            self.items = its

    items = ["안전복장 미착용인가?", "크레인 작업반경 내 무단출입인가?"]
    categories = [
        _Cat("PPE_MISSING", "보호장비 미착용", ["안전복장 미착용인가?"]),
        _Cat("ACCESS_VIOLATION", "출입통제 위반", ["크레인 작업반경 내 무단출입인가?"]),
    ]
    result = _format_checklist(items, categories)

    assert "1. 안전복장 미착용인가?" in result
    assert "2. 크레인 작업반경 내 무단출입인가?" in result
    assert "[" not in result   # 코드 태그 없어야 함
    assert result.count("\n") == 1


def test_format_checklist_without_categories_returns_numbered():
    """categories 없어도 번호 형식으로 반환."""
    from app.api.manuals import _format_checklist

    items = ["항목1?", "항목2?"]
    result = _format_checklist(items, [])

    assert "1. 항목1?" in result
    assert "2. 항목2?" in result
    assert "[" not in result


def test_format_checklist_single_item():
    """항목 1개도 정상 처리."""
    from app.api.manuals import _format_checklist
    result = _format_checklist(["항목1?"], [])
    assert result == "1. 항목1?"


def test_format_checklist_empty_items():
    """빈 items면 빈 문자열 반환."""
    from app.api.manuals import _format_checklist
    assert _format_checklist([], []) == ""
