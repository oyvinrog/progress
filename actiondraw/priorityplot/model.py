"""Priority plotting score utilities."""

from __future__ import annotations

import math


MIN_TIME_HOURS = 1.01


def clamp_time_hours(value: float) -> float:
    """Clamp time to a domain where ln(time) is positive and finite."""
    return max(MIN_TIME_HOURS, float(value))


def clamp_subjective_value(value: float) -> float:
    """Prevent negative subjective values from inverting priorities."""
    return max(0.0, float(value))


def normalize_priority_weight(value) -> float:
    """Default invalid importance weights to 1 and constrain them to 0–2."""
    try:
        weight = float(value)
    except (TypeError, ValueError, OverflowError):
        return 1.0
    return max(0.0, min(2.0, weight)) if math.isfinite(weight) else 1.0


def compute_priority_score(subjective_value: float, time_hours: float,
                           value_weight: float = 1.0, time_weight: float = 1.0) -> float:
    """Weighted value / ln(time); a zero exponent ignores that factor."""
    clamped_time = clamp_time_hours(time_hours)
    denominator = math.log(clamped_time)
    if denominator <= 0.0:
        return 0.0
    return (clamp_subjective_value(subjective_value) ** normalize_priority_weight(value_weight)
            / denominator ** normalize_priority_weight(time_weight))
