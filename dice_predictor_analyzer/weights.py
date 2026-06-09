"""Adaptive weighted ensemble for analyzer score streams."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class AdaptiveWeightSystem:
    """Self-learning multiplicative weight updater.

    Each analyzer is rewarded according to the probability it assigned to the
    actually observed next sum. We keep a floor to avoid permanently removing an
    analyzer after a short bad streak.
    """

    analyzer_names: list[str]
    learning_rate: float = 0.18
    min_weight: float = 0.04
    _weights: dict[str, float] = field(init=False, repr=False)
    _last_predictions: dict[str, dict[int, float]] | None = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        equal = 1.0 / len(self.analyzer_names)
        self._weights = {name: equal for name in self.analyzer_names}

    @property
    def weights(self) -> dict[str, float]:
        return dict(self._weights)

    def remember_predictions(self, predictions: dict[str, dict[int, float]]) -> None:
        self._last_predictions = {name: dict(scores) for name, scores in predictions.items()}

    def learn_from_actual(self, actual_sum: int) -> None:
        if not self._last_predictions:
            return
        baseline = 1.0 / 11.0
        for name, scores in self._last_predictions.items():
            hit_score = max(0.0, scores.get(actual_sum, 0.0))
            relative = (hit_score - baseline) / baseline
            multiplier = 1.0 + self.learning_rate * relative
            self._weights[name] = max(self.min_weight, self._weights.get(name, 0.0) * max(0.5, multiplier))
        self._normalize()

    def reset(self) -> None:
        equal = 1.0 / len(self.analyzer_names)
        self._weights = {name: equal for name in self.analyzer_names}
        self._last_predictions = None

    def _normalize(self) -> None:
        total = sum(self._weights.values())
        if total <= 0:
            self.reset()
            return
        self._weights = {name: weight / total for name, weight in self._weights.items()}
