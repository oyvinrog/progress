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


def compute_priority_score(subjective_value: float, time_hours: float) -> float:
    """Compute score as value / ln(time_hours) using natural log."""
    clamped_time = clamp_time_hours(time_hours)
    denominator = math.log(clamped_time)
    if denominator <= 0.0:
        return 0.0
    return clamp_subjective_value(subjective_value) / denominator
