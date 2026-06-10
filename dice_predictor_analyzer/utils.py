"""Small numeric helpers used by analytics and prediction modules."""

from __future__ import annotations

from .model import SUMS


def normalize_scores(scores: dict[int, float]) -> dict[int, float]:
    values = {total: max(0.0, float(scores.get(total, 0.0))) for total in SUMS}
    total_value = sum(values.values())
    if total_value <= 0:
        equal = 1.0 / len(list(SUMS))
        return {total: equal for total in SUMS}
    return {total: value / total_value for total, value in values.items()}


def min_max_scale(values: dict[int, float]) -> dict[int, float]:
    completed = {total: float(values.get(total, 0.0)) for total in SUMS}
    low = min(completed.values())
    high = max(completed.values())
    if high == low:
        return {total: 1.0 for total in SUMS}
    return {total: (value - low) / (high - low) for total, value in completed.items()}


def pct(value: float) -> str:
    return f"{value * 100:.1f}%"
