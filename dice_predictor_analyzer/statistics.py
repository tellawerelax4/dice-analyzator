"""Quality statistics and rolling prediction journal."""

from __future__ import annotations

from collections import deque
from dataclasses import replace
from datetime import datetime

from .model import MAX_PREDICTION_LOG, PredictionSnapshot


class StatisticsEngine:
    """Stores pre-roll forecasts and calculates TOP-1/TOP-3/TOP-5 hit rates."""

    def __init__(self) -> None:
        self._pending: PredictionSnapshot | None = None
        self._log: deque[PredictionSnapshot] = deque(maxlen=MAX_PREDICTION_LOG)
        self._top1_hits = 0
        self._top3_hits = 0
        self._top5_hits = 0
        self._settled = 0

    @property
    def log(self) -> list[PredictionSnapshot]:
        return list(self._log)

    def remember_forecast(self, top5: list[tuple[int, float]], confidence: float) -> None:
        if top5:
            self._pending = PredictionSnapshot(datetime.now(), list(top5), confidence)

    def settle_actual(self, actual: int) -> None:
        if self._pending is None:
            return
        forecast = replace(self._pending, actual=actual)
        top_values = [value for value, _score in forecast.top5]
        self._settled += 1
        if actual in top_values[:1]:
            self._top1_hits += 1
        if actual in top_values[:3]:
            self._top3_hits += 1
        if actual in top_values[:5]:
            self._top5_hits += 1
        self._log.appendleft(forecast)
        self._pending = None

    def accuracy(self) -> dict[str, float]:
        if self._settled == 0:
            return {"TOP-1": 0.0, "TOP-3": 0.0, "TOP-5": 0.0}
        return {
            "TOP-1": self._top1_hits / self._settled,
            "TOP-3": self._top3_hits / self._settled,
            "TOP-5": self._top5_hits / self._settled,
        }
