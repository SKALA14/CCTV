# services/inference/dynamic/trigger.py
"""Dual-EMA 기반 실시간 트리거 선별기.

프레임별 시각 feature를 fast/slow EMA로 추적해, 두 EMA의 차이(shift)가
평소보다 커지는 '신규성(novelty)' 구간만 VLM 호출 후보로 admit한다.
중복·쿨다운·예산(token bucket) 게이트로 과호출을 억제한다.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Iterable, Mapping


# 원시 feature를 0~1로 정규화할 때의 상한(cap). 값이 cap이면 정규화 결과 ≈1.
SCALE_CAPS = {
    "foreground_delta": 0.05,
    "foreground_residual_flow_p90": 6.0,
    "foreground_ratio": 0.25,
    "component_count": 12.0,
}

# fast-slow EMA 차이(shift)를 0~1로 정규화할 때의 상한.
SHIFT_CAPS = {
    "appearance": 0.12,
    "motion": 0.12,
    "foreground": 0.10,
    "component": 0.10,
}

# 최종 score 계산 시 source별 가중치(합 1.0).
SCORE_WEIGHTS = {
    "motion": 0.40,
    "appearance": 0.30,
    "foreground": 0.20,
    "component": 0.10,
}

# source가 '활성'으로 인정되는 (level 하한, shift 하한) 임계값.
ACTIVE_SOURCE_THRESHOLDS = {
    "appearance": (0.25, 0.45),
    "motion": (0.25, 0.45),
    "foreground": (0.18, 0.45),
    "component": (0.20, 0.45),
}


@dataclass(frozen=True)
class TriggerConfig:
    """트리거 선별 동작을 조절하는 튜닝 파라미터 모음."""
    warmup_sec: float = 2.0                   # 시작 후 이 시간 동안은 admit 안 함(EMA 안정화 대기)
    fast_tau_sec: float = 1.0                 # fast EMA 시정수(짧을수록 최근 변화에 민감)
    slow_tau_sec: float = 15.0                # slow EMA 시정수(장기 평소 상태 기준선)
    score_threshold: float = 0.35             # 후보 인정 최소 score (+ active source 2개 이상)
    strong_score_threshold: float = 0.55      # 단일 강한 source만으로 후보 인정하는 score
    strong_shift_threshold: float = 0.85      # 'strong source'로 보는 shift 하한
    min_component_share: float = 0.35         # 유효 전경: 최대 컴포넌트가 전경에서 차지하는 비율
    min_component_ratio: float = 0.001        # 유효 전경: 최대 컴포넌트/전체 픽셀 비율
    min_foreground_ratio: float = 0.003       # 유효 전경: 전경/전체 픽셀 비율
    transition_jump_threshold: float = 0.15   # 직전 후보 대비 score가 이만큼 튀면 새 전이로 인정
    duplicate_memory_sec: float = 5.0         # 최근 admit 기억 보관 시간(중복 비교용)
    duplicate_source_overlap: float = 0.67    # source 겹침이 이 이상이면 같은 source로 간주
    duplicate_score_jump: float = 0.20        # score 증가가 이 미만이면 중복 후보로 간주
    duplicate_foreground_delta: float = 0.03  # 전경 비율 변화가 이 미만이면 유사 형상
    duplicate_component_delta: float = 0.15   # 컴포넌트 레벨 변화가 이 미만이면 유사 형상
    low_novelty_threshold: float = 0.30       # mask_novelty가 이 미만이면 '새롭지 않음'으로 판단
    cooldown_sec: float = 0.0                 # admit 후 재admit 억제 시간(0=비활성)
    max_triggers_per_min: float = 0.0         # 분당 최대 admit 수(0=무제한)
    token_bucket_size: float = 2.0            # 토큰 버킷 용량(순간 버스트 허용량)


class RealtimeTriggerSelector:
    """인과적(causal) 트리거 선별기 — 미래 프레임을 보지 않고 순차적으로 처리한다.

    입력 row는 timestamp 순서로 들어와야 하며, _scaled_levels()가 사용하는 feature 키를 포함해야 한다.
    """

    def __init__(self, config: TriggerConfig = TriggerConfig()) -> None:
        self.config = config
        self.refill_per_sec = config.max_triggers_per_min / 60.0 if config.max_triggers_per_min > 0 else math.inf
        self.fast: dict[str, float] = {}
        self.slow: dict[str, float] = {}
        self.tokens = config.token_bucket_size if math.isfinite(self.refill_per_sec) else math.inf
        self.last_time: float | None = None
        self.last_admit_time = -math.inf
        self.recent_admits: list[dict[str, Any]] = []
        self.previous_candidate_raw = False
        self.previous_candidate_sources: set[str] = set()
        self.previous_candidate_score = 0.0

    def process(self, row: Mapping[str, Any]) -> dict[str, Any]:
        """프레임 1개의 feature row를 받아 EMA 갱신·점수화·게이트를 거쳐 admit 여부를 판정한다."""
        config = self.config
        timestamp = _float(row["timestamp_sec"])
        dt = 0.0 if self.last_time is None else max(0.0, timestamp - self.last_time)
        self.last_time = timestamp
        if math.isfinite(self.tokens):
            self.tokens = min(config.token_bucket_size, self.tokens + dt * self.refill_per_sec)

        levels = _scaled_levels(row)
        if not self.fast:
            self.fast = dict(levels)
            self.slow = dict(levels)

        # fast/slow EMA 갱신: 둘의 차이(shift)가 '평소 대비 급변' = 신규성 신호.
        fast_alpha = _ema_alpha(dt, config.fast_tau_sec)
        slow_alpha = _ema_alpha(dt, config.slow_tau_sec)
        for name, value in levels.items():
            self.fast[name] = self.fast[name] + fast_alpha * (value - self.fast[name])
            self.slow[name] = self.slow[name] + slow_alpha * (value - self.slow[name])

        # shift(=fast-slow)를 정규화해 가중합으로 score 산출, 활성 source도 판정.
        shift_raw = {
            name: max(0.0, self.fast[name] - self.slow[name])
            for name in ["appearance", "motion", "foreground", "component"]
        }
        shift_norm = {name: min(1.0, shift_raw[name] / SHIFT_CAPS[name]) for name in shift_raw}
        score = sum(SCORE_WEIGHTS[name] * shift_norm[name] for name in SCORE_WEIGHTS)
        active_sources = _active_sources(levels, shift_norm)
        source_count = len(active_sources)
        strong_source = any(shift_norm[name] >= config.strong_shift_threshold for name in shift_norm)

        valid_foreground = (
            _float(row["foreground_ratio"]) >= config.min_foreground_ratio
            and _float(row["largest_component_ratio"]) >= config.min_component_ratio
            and _float(row["largest_component_share"]) >= config.min_component_share
        )
        # warmup이 끝나고, 유효 전경이며, score 조건을 만족해야 후보(candidate_raw).
        warmup = int(row.get("warmup", 0)) == 1 or timestamp < config.warmup_sec
        candidate_raw = (
            not warmup
            and valid_foreground
            and (
                (score >= config.score_threshold and source_count >= 2)
                or (score >= config.strong_score_threshold and strong_source)
            )
        )

        # 같은 상황의 지속이 아니라 '새로 시작/변화한' 후보만 전이(transition)로 인정.
        source_changed = bool(active_sources != self.previous_candidate_sources)
        score_transition_jump = score - self.previous_candidate_score
        candidate_transition = candidate_raw and (
            not self.previous_candidate_raw
            or source_changed
            or score_transition_jump >= config.transition_jump_threshold
        )

        # 전이 후보를 중복 → 쿨다운 → 예산(token) 순으로 차례로 억제하고, 모두 통과해야 admit.
        self.recent_admits = [
            item
            for item in self.recent_admits
            if timestamp - float(item["timestamp_sec"]) <= config.duplicate_memory_sec
        ]
        duplicate_suppressed = candidate_transition and self._is_duplicate_candidate(
            row=row,
            score=score,
            active_sources=active_sources,
            levels=levels,
        )
        cooldown_suppressed = (
            candidate_transition
            and not duplicate_suppressed
            and timestamp - self.last_admit_time < config.cooldown_sec
        )
        budget_suppressed = (
            candidate_transition
            and not duplicate_suppressed
            and not cooldown_suppressed
            and math.isfinite(self.tokens)
            and self.tokens < 1.0
        )
        admitted = (
            candidate_transition
            and not duplicate_suppressed
            and not cooldown_suppressed
            and not budget_suppressed
        )

        if admitted:
            if math.isfinite(self.tokens):
                self.tokens -= 1.0
            self.last_admit_time = timestamp
            self.recent_admits.append(
                {
                    "timestamp_sec": timestamp,
                    "score": score,
                    "sources": set(active_sources),
                    "foreground_ratio": _float(row["foreground_ratio"]),
                    "component_level": levels["component"],
                }
            )

        if candidate_raw:
            self.previous_candidate_sources = set(active_sources)
            self.previous_candidate_score = score
        else:
            self.previous_candidate_sources = set()
            self.previous_candidate_score = 0.0
        self.previous_candidate_raw = bool(candidate_raw)

        return {
            "timestamp_sec": timestamp,
            "frame_index": row.get("frame_index", ""),
            "valid_foreground": int(valid_foreground),
            "activity_appearance": levels["appearance"],
            "activity_motion": levels["motion"],
            "activity_foreground": levels["foreground"],
            "activity_component": levels["component"],
            "fast_appearance": self.fast["appearance"],
            "fast_motion": self.fast["motion"],
            "fast_foreground": self.fast["foreground"],
            "fast_component": self.fast["component"],
            "slow_appearance": self.slow["appearance"],
            "slow_motion": self.slow["motion"],
            "slow_foreground": self.slow["foreground"],
            "slow_component": self.slow["component"],
            "shift_appearance": shift_norm["appearance"],
            "shift_motion": shift_norm["motion"],
            "shift_foreground": shift_norm["foreground"],
            "shift_component": shift_norm["component"],
            "dual_ema_score": score,
            "source_count": source_count,
            "active_sources": ",".join(sorted(active_sources)),
            "candidate_raw": int(candidate_raw),
            "candidate_transition": int(candidate_transition),
            "source_changed": int(source_changed),
            "score_transition_jump": score_transition_jump,
            "duplicate_suppressed": int(duplicate_suppressed),
            "cooldown_suppressed": int(cooldown_suppressed),
            "budget_suppressed": int(budget_suppressed),
            "admitted_trigger": int(admitted),
            "tokens": self.tokens if math.isfinite(self.tokens) else "",
        }

    def _is_duplicate_candidate(
        self,
        *,
        row: Mapping[str, Any],
        score: float,
        active_sources: set[str],
        levels: Mapping[str, float],
    ) -> bool:
        """최근 admit과 source·score 증가·형상이 모두 비슷하면 중복 후보로 판정한다."""
        config = self.config
        if not self.recent_admits:
            return False

        current_sources = set(active_sources)
        for previous in self.recent_admits:
            previous_sources = set(previous["sources"])
            source_union = len(current_sources | previous_sources)
            source_overlap = len(current_sources & previous_sources) / float(max(1, source_union))
            same_sources = source_overlap >= config.duplicate_source_overlap
            score_jump = score - float(previous["score"])
            foreground_delta = abs(_float(row["foreground_ratio"]) - float(previous["foreground_ratio"]))
            component_delta = abs(levels["component"] - float(previous["component_level"]))
            low_novelty = _float(row.get("mask_novelty")) < config.low_novelty_threshold
            similar_geometry = (
                foreground_delta < config.duplicate_foreground_delta
                and component_delta < config.duplicate_component_delta
            )
            if same_sources and score_jump < config.duplicate_score_jump and (low_novelty or similar_geometry):
                return True
        return False


def score_rows(rows: Iterable[Mapping[str, Any]], config: TriggerConfig = TriggerConfig()) -> list[dict[str, Any]]:
    """오프라인 헬퍼: row들의 실제 timestamp로 EMA alpha를 계산해 일괄 처리한다."""
    selector = RealtimeTriggerSelector(config)
    return [selector.process(row) for row in rows]


def _scaled_levels(row: Mapping[str, Any]) -> dict[str, float]:
    """원시 feature를 source별(appearance/motion/foreground/component) 0~1 활동량으로 변환한다."""
    foreground_delta = _bounded_norm(_float(row["foreground_delta"]), cap=SCALE_CAPS["foreground_delta"])
    foreground_ratio = _bounded_norm(_float(row["foreground_ratio"]), cap=SCALE_CAPS["foreground_ratio"])
    return {
        "appearance": min(1.0, max(0.0, _float(row["appearance_change"]))),
        "motion": _bounded_norm(
            _float(row["foreground_residual_flow_p90"]),
            cap=SCALE_CAPS["foreground_residual_flow_p90"],
        ),
        "foreground": max(foreground_delta, foreground_ratio),
        "component": _bounded_norm(_float(row["component_count"]), cap=SCALE_CAPS["component_count"]),
    }


def _active_sources(levels: Mapping[str, float], shift_norm: Mapping[str, float]) -> set[str]:
    """level과 shift가 모두 임계값을 넘는 source 집합을 반환한다."""
    sources = set()
    for name, (level_floor, shift_floor) in ACTIVE_SOURCE_THRESHOLDS.items():
        if levels[name] >= level_floor and shift_norm[name] >= shift_floor:
            sources.add(name)
    return sources


def _bounded_norm(value: float, *, cap: float) -> float:
    """값을 log 스케일로 0~1로 정규화한다(value가 cap이면 ≈1)."""
    if cap <= 0:
        return 0.0
    return min(1.0, math.log1p(max(0.0, value)) / math.log1p(cap))


def _ema_alpha(sample_period_sec: float, tau_sec: float) -> float:
    """샘플 간격과 시정수(tau)로 EMA 평활 계수(alpha)를 계산한다."""
    if tau_sec <= 0:
        return 1.0
    return 1.0 - math.exp(-sample_period_sec / tau_sec)


def _float(value: Any) -> float:
    """안전 float 변환 — None·빈 문자열·비정상(NaN/inf) 값은 0.0으로 처리한다."""
    if value in (None, ""):
        return 0.0
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return 0.0
    return parsed if math.isfinite(parsed) else 0.0
