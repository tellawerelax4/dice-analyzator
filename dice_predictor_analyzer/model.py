"""Core constants and value objects for Rondo/Twist sum analysis."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

MIN_SUM = 2
MAX_SUM = 12
SUMS = range(MIN_SUM, MAX_SUM + 1)
MIN_ROLLS_FOR_ANALYSIS = 15
MAX_PREDICTION_LOG = 100

THEORETICAL_SUM_COUNTS: dict[int, int] = {
    2: 1,
    3: 2,
    4: 3,
    5: 4,
    6: 5,
    7: 6,
    8: 5,
    9: 4,
    10: 3,
    11: 2,
    12: 1,
}
THEORETICAL_SUM_PROBS: dict[int, float] = {
    total: count / 36.0 for total, count in THEORETICAL_SUM_COUNTS.items()
}


@dataclass(frozen=True, slots=True)
class RollRecord:
    """One collected Rondo/Twist result from the site's history DOM."""

    total: int
    created_at: datetime

    def __post_init__(self) -> None:
        if self.total not in SUMS:
            raise ValueError("Roll total must be an integer from 2 to 12.")

    def label(self, index: int) -> str:
        return f"#{index}  {self.total}"


@dataclass(frozen=True, slots=True)
class PredictionSnapshot:
    """Forecast saved before the next actual result is known."""

    created_at: datetime
    top5: list[tuple[int, float]]
    confidence: float
    actual: int | None = None
