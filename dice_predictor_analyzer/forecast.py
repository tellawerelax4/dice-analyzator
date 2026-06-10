"""Prediction and analytics engine for collected Rondo/Twist sums."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from .analyzers import (
    BaseAnalyzer,
    DistributionBiasAnalyzer,
    FrequencyAnalyzer,
    LocalTrendAnalyzer,
    RecencyAnalyzer,
    StreakAnalyzer,
    TransitionAnalyzer,
    absence_map,
    current_parity_streak,
    current_range_streak,
    current_same_streak,
    longest_same_streak,
)
from .model import MIN_ROLLS_FOR_ANALYSIS, SUMS, THEORETICAL_SUM_PROBS
from .statistics import StatisticsEngine
from .utils import normalize_scores
from .weights import AdaptiveWeightsEngine


@dataclass(frozen=True, slots=True)
class Forecast:
    enabled: bool
    message: str
    top5: list[tuple[int, float]]
    combined_scores: dict[int, float]
    algorithm_scores: dict[str, dict[int, float]]
    range_probs: dict[str, float]
    parity_probs: dict[str, float]
    signal_strength: float
    weights: dict[str, float]
    insights: list[str]
    theory_rows: list[tuple[int, float, float, float, int]]
    hot: list[tuple[int, int]]
    cold: list[tuple[int, int]]
    absent: list[tuple[int, int]]


class PredictionEngine:
    """Runs six sum-only analyzers and combines them with adaptive weights."""

    def __init__(self, statistics: StatisticsEngine | None = None) -> None:
        self.analyzers: list[BaseAnalyzer] = [
            FrequencyAnalyzer(),
            RecencyAnalyzer(),
            TransitionAnalyzer(),
            LocalTrendAnalyzer(),
            StreakAnalyzer(),
            DistributionBiasAnalyzer(),
        ]
        self.weights = AdaptiveWeightsEngine([analyzer.name for analyzer in self.analyzers])
        self.statistics = statistics or StatisticsEngine()
        self.signal_history: list[float] = []
        self.last_forecast: Forecast | None = None

    def process_new_result(self, totals: list[int], actual: int) -> Forecast:
        self.statistics.settle_actual(actual)
        self.weights.learn_from_actual(actual)
        forecast = self.forecast(totals)
        if forecast.enabled:
            self.statistics.remember_forecast(forecast.top5, forecast.signal_strength)
        return forecast

    def forecast(self, totals: list[int]) -> Forecast:
        if len(totals) < MIN_ROLLS_FOR_ANALYSIS:
            message = f"Недостаточно данных для анализа.\nСобрано {len(totals)} из {MIN_ROLLS_FOR_ANALYSIS} бросков."
            forecast = self._build_disabled(totals, message)
            self.last_forecast = forecast
            return forecast

        analyzer_results = [analyzer.analyze(totals) for analyzer in self.analyzers]
        algorithm_scores = {result.name: result.scores for result in analyzer_results}
        combined_raw = {total: 0.0 for total in SUMS}
        for result in analyzer_results:
            weight = self.weights.weights[result.name]
            for total, score in result.scores.items():
                combined_raw[total] += weight * score
        combined = normalize_scores(combined_raw)
        self.weights.remember_predictions(algorithm_scores)
        top5 = sorted(combined.items(), key=lambda item: item[1], reverse=True)[:5]
        signal = self._signal_strength(combined)
        self.signal_history.append(signal)
        self.signal_history = self.signal_history[-300:]
        forecast = Forecast(
            enabled=True,
            message="Анализ активен",
            top5=top5,
            combined_scores=combined,
            algorithm_scores=algorithm_scores,
            range_probs=self._range_probs(combined),
            parity_probs=self._parity_probs(combined),
            signal_strength=signal,
            weights=self.weights.weights,
            insights=self._insights(totals),
            theory_rows=self._theory_rows(totals),
            hot=self._hot(totals),
            cold=self._cold(totals),
            absent=sorted(absence_map(totals).items(), key=lambda item: item[1], reverse=True)[:5],
        )
        self.last_forecast = forecast
        return forecast

    def _build_disabled(self, totals: list[int], message: str) -> Forecast:
        combined = normalize_scores({total: THEORETICAL_SUM_PROBS[total] for total in SUMS})
        return Forecast(
            False,
            message,
            [],
            combined,
            {},
            self._range_probs(combined),
            self._parity_probs(combined),
            0.0,
            self.weights.weights,
            self._insights(totals) if totals else [],
            self._theory_rows(totals),
            self._hot(totals),
            self._cold(totals),
            sorted(absence_map(totals).items(), key=lambda item: item[1], reverse=True)[:5],
        )

    @staticmethod
    def _range_probs(scores: dict[int, float]) -> dict[str, float]:
        ranges = {
            "2-6": sum(scores[total] for total in range(2, 7)),
            "7": scores[7],
            "8-12": sum(scores[total] for total in range(8, 13)),
        }
        total = sum(ranges.values()) or 1.0
        return {name: value / total for name, value in ranges.items()}

    @staticmethod
    def _parity_probs(scores: dict[int, float]) -> dict[str, float]:
        parity = {
            "Чётное": sum(scores[total] for total in SUMS if total % 2 == 0),
            "Нечётное": sum(scores[total] for total in SUMS if total % 2 == 1),
        }
        total = sum(parity.values()) or 1.0
        return {name: value / total for name, value in parity.items()}

    @staticmethod
    def _signal_strength(scores: dict[int, float]) -> float:
        ordered = sorted(scores.values(), reverse=True)
        if len(ordered) < 2:
            return 0.0
        leader_gap = max(0.0, ordered[0] - ordered[1])
        mean_gap = sum(max(0.0, ordered[0] - value) for value in ordered[1:]) / (len(ordered) - 1)
        return min(1.0, (leader_gap * 6.0 + mean_gap * 3.0))

    @staticmethod
    def _hot(totals: list[int]) -> list[tuple[int, int]]:
        counter = Counter(totals[-20:])
        return counter.most_common(5)

    @staticmethod
    def _cold(totals: list[int]) -> list[tuple[int, int]]:
        counter = Counter(totals[-20:])
        return sorted(((total, counter[total]) for total in SUMS), key=lambda item: (item[1], item[0]))[:5]

    @staticmethod
    def _theory_rows(totals: list[int]) -> list[tuple[int, float, float, float, int]]:
        counter = Counter(totals)
        denominator = max(1, len(totals))
        rows = []
        for total in SUMS:
            theory = THEORETICAL_SUM_PROBS[total]
            fact = counter[total] / denominator if totals else 0.0
            rows.append((total, theory, fact, fact - theory, counter[total]))
        return rows

    @staticmethod
    def _insights(totals: list[int]) -> list[str]:
        if not totals:
            return ["Ожидание результатов из DOM истории."]
        insights: list[str] = []
        same = current_same_streak(totals)
        parity = current_parity_streak(totals)
        range_streak = current_range_streak(totals)
        longest = longest_same_streak(totals)
        insights.append(f"Текущая серия суммы: {same[0]} × {same[1]}.")
        insights.append(f"Текущая серия чёт/нечёт: {parity[0]} × {parity[1]}.")
        insights.append(f"Текущая серия диапазона: {range_streak[0]} × {range_streak[1]}.")
        if longest:
            insights.append(f"Самая длинная серия одинаковых сумм: {longest[0]} × {longest[1]}.")
        transitions = Counter(zip(totals, totals[1:], strict=False))
        if transitions:
            insights.append("Частые переходы: " + ", ".join(f"{a}→{b} ({c})" for (a, b), c in transitions.most_common(5)) + ".")
            last = totals[-1]
            after_last = Counter(current for previous, current in zip(totals, totals[1:], strict=False) if previous == last)
            if after_last:
                next_sum, count = after_last.most_common(1)[0]
                insights.append(f"После {last} чаще всего выпадало {next_sum} ({count} раз).")
        return insights
