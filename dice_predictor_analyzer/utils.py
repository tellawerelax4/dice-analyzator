"""Shared numerical helpers."""

from __future__ import annotations

from collections.abc import Mapping

from .model import SUMS


def normalize_scores(scores: Mapping[int, float], *, default: float | None = None) -> dict[int, float]:
    """Return non-negative scores normalized to sum to 1 across all dice sums."""

    cleaned = {total: max(0.0, float(scores.get(total, 0.0))) for total in SUMS}
    score_sum = sum(cleaned.values())
    if score_sum <= 0:
        fallback = 1.0 / len(tuple(SUMS)) if default is None else default
        return {total: fallback for total in SUMS}
    return {total: value / score_sum for total, value in cleaned.items()}


def min_max_scale(values: Mapping[int, float]) -> dict[int, float]:
    """Scale values to a 0..1 range while preserving all sum keys."""

    cleaned = {total: float(values.get(total, 0.0)) for total in SUMS}
    low = min(cleaned.values())
    high = max(cleaned.values())
    if high == low:
        return {total: 1.0 for total in SUMS}
    return {total: (value - low) / (high - low) for total, value in cleaned.items()}
