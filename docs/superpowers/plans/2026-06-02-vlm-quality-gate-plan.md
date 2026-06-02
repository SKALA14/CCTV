# VLM Quality Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** VLM 이벤트 발행 전 Confidence Gate + Cross-pipeline Dedup을 추가해 저확신 오탐 억제 및 파이프라인 간 중복 제거

**Architecture:** `vlm/gate.py` 공통 모듈에 gate 로직 집약, Static/Dynamic worker에서 import. 모든 임계값은 config.py 환경변수. Emergency는 대상 아님.

**Tech Stack:** Python 3.11, Redis sync client, pydantic-settings, pytest

---

### Task 1: config.py에 MIN_CONFIDENCE, DEDUP_TTL_SEC 추가

**Files:**
- Modify: `services/inference/config.py:64-71` (Static 섹션 근처)

- [ ] **Step 1: config.py에 설정값 추가**

`services/inference/config.py` Settings 클래스에 두 필드 추가:

```python
# Quality Gate
MIN_CONFIDENCE: float = 0.6
DEDUP_TTL_SEC: int = 60
```

`STATIC_INTERVAL_SEC` 위에, `# Quality Gate` 주석과 함께 삽입한다.

- [ ] **Step 2: 설정값 로드 확인**

```bash
cd /Users/skala/workspace/CCTV/services/inference && python -c "from config import config; print(config.MIN_CONFIDENCE, config.DEDUP_TTL_SEC)"
```

Expected: `0.6 60`

- [ ] **Step 3: Commit**

```bash
git add services/inference/config.py
git commit -m "feat: add MIN_CONFIDENCE and DEDUP_TTL_SEC config"
```

---

### Task 2: vlm/gate.py TDD 구현

**Files:**
- Create: `services/inference/vlm/gate.py`
- Create: `services/inference/tests/test_gate.py`

- [ ] **Step 1: 테스트 파일 작성**

`services/inference/tests/test_gate.py`:

```python
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
```

- [ ] **Step 2: 테스트 실행 — 실패 확인**

```bash
cd /Users/skala/workspace/CCTV/services/inference && python -m pytest tests/test_gate.py -v
```

Expected: ModuleNotFoundError (vlm.gate 없음)

- [ ] **Step 3: gate.py 구현**

`services/inference/vlm/gate.py`:

```python
"""VLM 이벤트 발행 전 Quality Gate.

Confidence Gate: 저확신 anomaly 억제
Cross-pipeline Dedup: 동일 카메라 중복 이벤트 억제
"""

from __future__ import annotations

import logging

from config import config
from redis_client import get_client

logger = logging.getLogger(__name__)


def should_publish(result: dict, camera_id: str, pipeline: str) -> bool:
    """Confidence Gate + Dedup Check 순차 적용.

    True면 이벤트 발행 허용, False면 억제.
    normal 결과는 Gate 없이 True 반환 (기존 동작 유지).
    """
    if result.get("result") != "anomaly":
        return True

    # --- Confidence Gate ---
    confidence = float(result.get("confidence", 0.0))
    threshold = config.MIN_CONFIDENCE
    # Future: camera:{camera_id}:min_confidence Redis key로 카메라별 오버라이드
    # Future: danger_level별 차등 임계값

    if confidence < threshold:
        logger.info(
            "[%s] SUPPRESSED cam=%s confidence=%.2f threshold=%.2f danger=%s type=%s",
            pipeline, camera_id, confidence, threshold,
            result.get("danger_level", "none"),
            result.get("anomaly_type", "GENERAL"),
        )
        return False

    # --- Cross-pipeline Dedup ---
    dedup_key = f"event:dedup:{camera_id}"
    try:
        existing = get_client().get(dedup_key)
    except Exception as e:
        logger.warning("[%s] dedup check 실패 cam=%s: %s (발행 허용)", pipeline, camera_id, e)
        return True

    if existing:
        try:
            ttl = get_client().ttl(dedup_key)
        except Exception:
            ttl = -1
        logger.info(
            "[%s] DEDUP_HIT cam=%s already_fired_by=%s ttl_remaining=%ds",
            pipeline, camera_id, existing, ttl,
        )
        return False

    # Future: danger_level == "critical" → dedup bypass
    # Future: violated_index가 다르면 dedup 면제

    return True


def mark_published(camera_id: str, pipeline: str) -> None:
    """이벤트 발행 성공 후 dedup 키 설정."""
    dedup_key = f"event:dedup:{camera_id}"
    try:
        get_client().setex(dedup_key, config.DEDUP_TTL_SEC, pipeline)
    except Exception as e:
        logger.warning("[%s] dedup 키 설정 실패 cam=%s: %s", pipeline, camera_id, e)
```

- [ ] **Step 4: 테스트 실행 — 통과 확인**

```bash
cd /Users/skala/workspace/CCTV/services/inference && python -m pytest tests/test_gate.py -v
```

Expected: 8 passed

- [ ] **Step 5: Commit**

```bash
git add services/inference/vlm/gate.py services/inference/tests/test_gate.py
git commit -m "feat: add vlm/gate.py — Confidence Gate + Cross-pipeline Dedup"
```

---

### Task 3: Static worker에 gate 적용

**Files:**
- Modify: `services/inference/static/vlm_worker.py:44-75`

- [ ] **Step 1: import 추가**

`services/inference/static/vlm_worker.py` 상단에 추가:

```python
from vlm.gate import should_publish, mark_published
```

- [ ] **Step 2: analyze_camera() 에 gate 호출 삽입**

현재 코드 (61-75줄):

```python
    if result.get("result") == "normal":
        logger.info("[static.vlm] ← normal (%.1fs): camera=%s", elapsed, camera_id)
        return

    xadd(config.EVENTS_STREAM, {
        ...
    }, maxlen=config.EVENTS_MAXLEN)
    logger.info("[static.vlm] ← anomaly (%.1fs): camera=%s type=%s",
                elapsed, camera_id, result.get("anomaly_type"))
```

변경 후:

```python
    if result.get("result") == "normal":
        logger.info("[static.vlm] ← normal (%.1fs): camera=%s", elapsed, camera_id)
        return

    if not should_publish(result, camera_id, "static"):
        return

    xadd(config.EVENTS_STREAM, {
        "camera_id": camera_id,
        "track": "static",
        "anomaly_type": result.get("anomaly_type", "normal"),
        "danger_level": result.get("danger_level", "none"),
        "description": result.get("description", ""),
        "timestamp": str(time.time()),
        "frame_path": frame_path,
    }, maxlen=config.EVENTS_MAXLEN)
    mark_published(camera_id, "static")
    logger.info("[static.vlm] ← anomaly (%.1fs): camera=%s type=%s",
                elapsed, camera_id, result.get("anomaly_type"))
```

- [ ] **Step 3: Commit**

```bash
git add services/inference/static/vlm_worker.py
git commit -m "feat: static worker — apply Confidence Gate + Dedup before event publish"
```

---

### Task 4: Dynamic worker에 gate 적용

**Files:**
- Modify: `services/inference/dynamic/vlm_worker.py:38-68`

- [ ] **Step 1: import 추가**

`services/inference/dynamic/vlm_worker.py` 상단에 추가:

```python
from vlm.gate import should_publish, mark_published
```

- [ ] **Step 2: run() 내 anomaly 분기에 gate 삽입**

현재 코드 (50-63줄):

```python
            if result.get("result") != "normal":
                with buffer_lock:
                    buffer.reset_cooldown(cam_id)
                xadd(config.EVENTS_STREAM, {
                    ...
                }, maxlen=config.EVENTS_MAXLEN)
                logger.info("[dynamic.vlm] ← anomaly (%.1fs): camera=%s type=%s",
                            elapsed, cam_id, result.get("anomaly_type"))
            else:
                logger.info("[dynamic.vlm] ← normal (%.1fs): camera=%s", elapsed, cam_id)
```

변경 후:

```python
            if result.get("result") != "normal":
                if not should_publish(result, cam_id, "dynamic"):
                    logger.info("[dynamic.vlm] ← gate filtered (%.1fs): camera=%s", elapsed, cam_id)
                else:
                    with buffer_lock:
                        buffer.reset_cooldown(cam_id)
                    xadd(config.EVENTS_STREAM, {
                        "camera_id": cam_id,
                        "track": "dynamic",
                        "anomaly_type": result.get("anomaly_type", "normal"),
                        "danger_level": result.get("danger_level", "none"),
                        "description": result.get("description", ""),
                        "timestamp": timestamp,
                        "frame_path": frame_paths[0],
                    }, maxlen=config.EVENTS_MAXLEN)
                    mark_published(cam_id, "dynamic")
                    logger.info("[dynamic.vlm] ← anomaly (%.1fs): camera=%s type=%s",
                                elapsed, cam_id, result.get("anomaly_type"))
            else:
                logger.info("[dynamic.vlm] ← normal (%.1fs): camera=%s", elapsed, cam_id)
```

주의: `should_publish()`는 sync 함수이고 Dynamic worker는 별도 스레드에서 실행되므로 문제없다. `buffer.reset_cooldown()`은 gate 통과 후에만 호출해야 한다 (억제된 이벤트로 쿨다운 리셋하면 안 됨).

- [ ] **Step 3: Commit**

```bash
git add services/inference/dynamic/vlm_worker.py
git commit -m "feat: dynamic worker — apply Confidence Gate + Dedup before event publish"
```

---

### Task 5: 통합 테스트 — 컨테이너 빌드 및 로그 확인

**Files:**
- No code changes — 빌드 및 검증

- [ ] **Step 1: inference 컨테이너 재빌드**

```bash
cd /Users/skala/workspace/CCTV/infra && docker compose build inference && docker compose up -d inference
```

- [ ] **Step 2: 컨테이너 정상 기동 확인**

```bash
cd /Users/skala/workspace/CCTV/infra && docker compose logs inference --tail=15
```

Expected: emergency, dynamic, static, cleaner 4개 프로세스 정상 시작

- [ ] **Step 3: config 기본값 확인**

```bash
docker compose exec inference python -c "from config import config; print('MIN_CONFIDENCE:', config.MIN_CONFIDENCE, 'DEDUP_TTL_SEC:', config.DEDUP_TTL_SEC)"
```

Expected: `MIN_CONFIDENCE: 0.6 DEDUP_TTL_SEC: 60`

- [ ] **Step 4: 영상 등록 후 로그에서 gate 동작 확인**

프론트엔드에서 채널을 등록하고 VLM 호출 로그를 확인:

```bash
docker compose logs -f inference 2>&1 | grep -E "SUPPRESSED|DEDUP_HIT|anomaly|normal"
```

정상 케이스:
- `[static.vlm] ← anomaly` + SUPPRESSED/DEDUP_HIT 없음 → 이벤트 발행됨
- `[static] SUPPRESSED` → 저확신 이벤트 억제됨
- `[dynamic] DEDUP_HIT` → static이 먼저 발행해 중복 억제됨
