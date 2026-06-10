"""Adaptive Weighted Ensemble implementation."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class AdaptiveWeightsEngine:
    """Online multiplicative weights updated after each known actual result."""

    analyzer_names: list[str]
    learning_rate: float = 0.18
    min_weight: float = 0.04
    _weights: dict[str, float] = field(init=False, repr=False)
    _last_predictions: dict[str, dict[int, float]] | None = field(default=None, init=False, repr=False)
    history: list[dict[str, float]] = field(default_factory=list, init=False)

    def __post_init__(self) -> None:
        equal = 1.0 / len(self.analyzer_names)
        self._weights = {name: equal for name in self.analyzer_names}
        self.history.append(dict(self._weights))

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
            multiplier = max(0.55, 1.0 + self.learning_rate * relative)
            self._weights[name] = max(self.min_weight, self._weights.get(name, 0.0) * multiplier)
        self._normalize()
        self.history.append(dict(self._weights))
        self.history = self.history[-300:]

    def reset(self) -> None:
        equal = 1.0 / len(self.analyzer_names)
        self._weights = {name: equal for name in self.analyzer_names}
        self._last_predictions = None
        self.history = [dict(self._weights)]

    def _normalize(self) -> None:
        total = sum(self._weights.values())
        if total <= 0:
            self.reset()
            return
        self._weights = {name: weight / total for name, weight in self._weights.items()}


AdaptiveWeightSystem = AdaptiveWeightsEngine
