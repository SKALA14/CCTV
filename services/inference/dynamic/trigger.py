from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Iterable, Mapping


SCALE_CAPS = {
    "foreground_delta": 0.05,
    "foreground_residual_flow_p90": 6.0,
    "foreground_ratio": 0.25,
    "component_count": 12.0,
}

SHIFT_CAPS = {
    "appearance": 0.12,
    "motion": 0.12,
    "foreground": 0.10,
    "component": 0.10,
}

SCORE_WEIGHTS = {
    "motion": 0.40,
    "appearance": 0.30,
    "foreground": 0.20,
    "component": 0.10,
}

ACTIVE_SOURCE_THRESHOLDS = {
    "appearance": (0.25, 0.45),
    "motion": (0.25, 0.45),
    "foreground": (0.18, 0.45),
    "component": (0.20, 0.45),
}


@dataclass(frozen=True)
class TriggerConfig:
    warmup_sec: float = 2.0
    fast_tau_sec: float = 1.0
    slow_tau_sec: float = 15.0
    score_threshold: float = 0.35
    strong_score_threshold: float = 0.55
    strong_shift_threshold: float = 0.85
    min_component_share: float = 0.35
    min_component_ratio: float = 0.001
    min_foreground_ratio: float = 0.003
    transition_jump_threshold: float = 0.15
    duplicate_memory_sec: float = 5.0
    duplicate_source_overlap: float = 0.67
    duplicate_score_jump: float = 0.20
    duplicate_foreground_delta: float = 0.03
    duplicate_component_delta: float = 0.15
    low_novelty_threshold: float = 0.30
    cooldown_sec: float = 0.0
    max_triggers_per_min: float = 0.0
    token_bucket_size: float = 2.0


class RealtimeTriggerSelector:
    """Causal trigger-point selector.

    Input rows must arrive in timestamp order and contain the feature keys used
    by _scaled_levels(). The selector does not use future frames.
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

        fast_alpha = _ema_alpha(dt, config.fast_tau_sec)
        slow_alpha = _ema_alpha(dt, config.slow_tau_sec)
        for name, value in levels.items():
            self.fast[name] = self.fast[name] + fast_alpha * (value - self.fast[name])
            self.slow[name] = self.slow[name] + slow_alpha * (value - self.slow[name])

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
        warmup = int(row.get("warmup", 0)) == 1 or timestamp < config.warmup_sec
        candidate_raw = (
            not warmup
            and valid_foreground
            and (
                (score >= config.score_threshold and source_count >= 2)
                or (score >= config.strong_score_threshold and strong_source)
            )
        )

        source_changed = bool(active_sources != self.previous_candidate_sources)
        score_transition_jump = score - self.previous_candidate_score
        candidate_transition = candidate_raw and (
            not self.previous_candidate_raw
            or source_changed
            or score_transition_jump >= config.transition_jump_threshold
        )

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
    """Offline helper: alphas are derived from actual per-row timestamps."""
    selector = RealtimeTriggerSelector(config)
    return [selector.process(row) for row in rows]


def _scaled_levels(row: Mapping[str, Any]) -> dict[str, float]:
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
    sources = set()
    for name, (level_floor, shift_floor) in ACTIVE_SOURCE_THRESHOLDS.items():
        if levels[name] >= level_floor and shift_norm[name] >= shift_floor:
            sources.add(name)
    return sources


def _bounded_norm(value: float, *, cap: float) -> float:
    if cap <= 0:
        return 0.0
    return min(1.0, math.log1p(max(0.0, value)) / math.log1p(cap))


def _ema_alpha(sample_period_sec: float, tau_sec: float) -> float:
    if tau_sec <= 0:
        return 1.0
    return 1.0 - math.exp(-sample_period_sec / tau_sec)


def _float(value: Any) -> float:
    if value in (None, ""):
        return 0.0
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return 0.0
    return parsed if math.isfinite(parsed) else 0.0
