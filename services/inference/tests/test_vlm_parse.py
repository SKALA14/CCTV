# services/inference/tests/test_vlm_parse.py
"""VLMClient._parse() 단위 테스트 — categories dict를 통한 violated_index 매핑."""
import sys
from pathlib import Path

# inference 서비스 루트를 경로에 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

from unittest.mock import patch


def _make_client():
    """Redis/OpenAI 없이 VLMClient 인스턴스 생성."""
    with patch("vlm.client.config") as mock_cfg:
        mock_cfg.OPENAI_API_KEY = "test-key"
        mock_cfg.OPENAI_MODEL = "gpt-4o"
        with patch("vlm.client.OpenAI"):
            from vlm.client import VLMClient
            return VLMClient()


def test_parse_violated_index_maps_to_code():
    """violated_index + categories → anomaly_type 코드 변환."""
    client = _make_client()
    raw = '{"result": "anomaly", "violated_index": "2", "danger_level": "high", "description": "위반 감지", "confidence": 0.9}'
    categories = {"1": "SAFETY_BARRIERS", "2": "SAFETY_SIGNS"}
    result = client._parse(raw, categories)
    assert result["anomaly_type"] == "SAFETY_SIGNS"
    assert result["result"] == "anomaly"


def test_parse_normal_result_returns_normal():
    """result=normal이면 violated_index 무관하게 anomaly_type=normal."""
    client = _make_client()
    raw = '{"result": "normal", "violated_index": null, "danger_level": "none", "description": "", "confidence": 0.1}'
    result = client._parse(raw, {"1": "SAFETY_BARRIERS"})
    assert result["result"] == "normal"
    assert result["anomaly_type"] == "normal"


def test_parse_out_of_range_index_returns_general():
    """categories에 없는 인덱스면 GENERAL fallback."""
    client = _make_client()
    raw = '{"result": "anomaly", "violated_index": "99", "danger_level": "low", "description": "알 수 없음", "confidence": 0.5}'
    categories = {"1": "SAFETY_BARRIERS"}
    result = client._parse(raw, categories)
    assert result["anomaly_type"] == "GENERAL"


def test_parse_empty_categories_uses_general():
    """categories 빈 dict면 anomaly_type=GENERAL."""
    client = _make_client()
    raw = '{"result": "anomaly", "violated_index": "1", "danger_level": "high", "description": "위반", "confidence": 0.8}'
    result = client._parse(raw, {})
    assert result["anomaly_type"] == "GENERAL"


def test_parse_no_categories_param_uses_general():
    """categories 파라미터 없으면 GENERAL fallback."""
    client = _make_client()
    raw = '{"result": "anomaly", "violated_index": "1", "danger_level": "high", "description": "위반", "confidence": 0.8}'
    result = client._parse(raw)
    assert result["anomaly_type"] == "GENERAL"


def test_parse_invalid_json_returns_normal():
    """JSON 파싱 실패 시 normal fallback."""
    client = _make_client()
    result = client._parse("not json at all", {"1": "CODE"})
    assert result["result"] == "normal"
    assert result["anomaly_type"] == "normal"
