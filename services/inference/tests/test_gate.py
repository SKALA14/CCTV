"""vlm/gate.py 단위 테스트."""

import pytest
from unittest.mock import patch, MagicMock

from vlm.gate import should_publish, mark_published


class TestConfidenceGate:
    """Confidence Gate 테스트."""

    def test_normal_result_passes(self):
        """result=normal이면 항상 True (gate 통과)."""
        result = {"result": "normal", "confidence": 0.1, "danger_level": "none"}
        assert should_publish(result, "cam0", "static") is True

    def test_anomaly_above_threshold_passes(self):
        """confidence >= MIN_CONFIDENCE이면 통과."""
        result = {"result": "anomaly", "confidence": 0.8, "danger_level": "high"}
        with patch("vlm.gate.config") as mock_config:
            mock_config.MIN_CONFIDENCE = 0.6
            mock_config.DEDUP_TTL_SEC = 60
            with patch("vlm.gate.get_client") as mock_redis:
                mock_redis.return_value.get.return_value = None
                assert should_publish(result, "cam0", "static") is True

    def test_anomaly_below_threshold_suppressed(self):
        """confidence < MIN_CONFIDENCE이면 억제."""
        result = {"result": "anomaly", "confidence": 0.4, "danger_level": "low"}
        with patch("vlm.gate.config") as mock_config:
            mock_config.MIN_CONFIDENCE = 0.6
            assert should_publish(result, "cam0", "static") is False

    def test_anomaly_exact_threshold_passes(self):
        """confidence == MIN_CONFIDENCE이면 통과."""
        result = {"result": "anomaly", "confidence": 0.6, "danger_level": "high"}
        with patch("vlm.gate.config") as mock_config:
            mock_config.MIN_CONFIDENCE = 0.6
            mock_config.DEDUP_TTL_SEC = 60
            with patch("vlm.gate.get_client") as mock_redis:
                mock_redis.return_value.get.return_value = None
                assert should_publish(result, "cam0", "static") is True


class TestDedupCheck:
    """Cross-pipeline Dedup 테스트."""

    def test_no_dedup_key_passes(self):
        """dedup 키 없으면 통과."""
        result = {"result": "anomaly", "confidence": 0.9, "danger_level": "high"}
        with patch("vlm.gate.config") as mock_config:
            mock_config.MIN_CONFIDENCE = 0.6
            mock_config.DEDUP_TTL_SEC = 60
            with patch("vlm.gate.get_client") as mock_redis:
                mock_redis.return_value.get.return_value = None
                assert should_publish(result, "cam0", "static") is True

    def test_existing_dedup_key_blocked(self):
        """dedup 키 존재하면 억제."""
        result = {"result": "anomaly", "confidence": 0.9, "danger_level": "high"}
        with patch("vlm.gate.config") as mock_config:
            mock_config.MIN_CONFIDENCE = 0.6
            mock_config.DEDUP_TTL_SEC = 60
            with patch("vlm.gate.get_client") as mock_redis:
                mock_client = mock_redis.return_value
                mock_client.get.return_value = "static"
                mock_client.ttl.return_value = 42
                assert should_publish(result, "cam0", "dynamic") is False

    def test_confidence_checked_before_dedup(self):
        """confidence 미달이면 dedup check까지 안 감 (Redis 호출 없음)."""
        result = {"result": "anomaly", "confidence": 0.3, "danger_level": "low"}
        with patch("vlm.gate.config") as mock_config:
            mock_config.MIN_CONFIDENCE = 0.6
            with patch("vlm.gate.get_client") as mock_redis:
                assert should_publish(result, "cam0", "static") is False
                mock_redis.return_value.get.assert_not_called()


class TestMarkPublished:
    """mark_published() 테스트."""

    def test_sets_dedup_key(self):
        """SETEX로 dedup 키 설정."""
        with patch("vlm.gate.config") as mock_config:
            mock_config.DEDUP_TTL_SEC = 60
            with patch("vlm.gate.get_client") as mock_redis:
                mark_published("cam0", "static")
                mock_redis.return_value.setex.assert_called_once_with(
                    "event:dedup:cam0", 60, "static"
                )

    def test_mark_published_handles_redis_error_silently(self):
        """Redis 장애 시 예외 없이 조용히 실패."""
        with patch("vlm.gate.config") as mock_config:
            mock_config.DEDUP_TTL_SEC = 60
            with patch("vlm.gate.get_client") as mock_redis:
                mock_redis.return_value.setex.side_effect = Exception("redis down")
                # Should not raise
                mark_published("cam0", "static")
