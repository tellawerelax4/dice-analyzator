"""Forecast orchestration and derived analytical summaries."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from .analyzers import AnalyzerResult, create_default_analyzers
from .model import MIN_ROLLS_FOR_ANALYSIS, SUMS, Roll, THEORETICAL_SUM_PROBS
from .utils import normalize_scores
from .weights import AdaptiveWeightSystem


@dataclass(frozen=True, slots=True)
class ForecastReport:
    enabled: bool
    roll_count: int
    message: str
    top5: list[tuple[int, float]]
    range_probabilities: dict[str, float]
    combined_scores: dict[int, float]
    analyzer_results: dict[str, AnalyzerResult]
    weights: dict[str, float]
    insights: list[str]
    theory_rows: list[tuple[int, float, float, float]]


class ForecastEngine:
    """Runs analyzers, trains adaptive weights, and combines predictions."""

    def __init__(self) -> None:
        self.analyzers = create_default_analyzers()
        self.weights = AdaptiveWeightSystem([analyzer.name for analyzer in self.analyzers])
        self._previous_len = 0

    def rebuild(self, rolls: list[Roll]) -> ForecastReport:
        """Fully recompute adaptive weights and current forecast from history."""

        self.weights.reset()
        self._previous_len = 0
        for index in range(MIN_ROLLS_FOR_ANALYSIS, len(rolls)):
            previous = rolls[:index]
            predictions = self._run_predictions(previous)
            self.weights.remember_predictions({name: result.scores for name, result in predictions.items()})
            self.weights.learn_from_actual(rolls[index].total)
        self._previous_len = len(rolls)
        return self.report(rolls)

    def report(self, rolls: list[Roll]) -> ForecastReport:
        roll_count = len(rolls)
        if roll_count < MIN_ROLLS_FOR_ANALYSIS:
            return ForecastReport(
                enabled=False,
                roll_count=roll_count,
                message=f"Недостаточно данных для анализа. Собрано {roll_count} из {MIN_ROLLS_FOR_ANALYSIS} бросков.",
                top5=[],
                range_probabilities={"2–6": 0.0, "7": 0.0, "8–12": 0.0},
                combined_scores={},
                analyzer_results={},
                weights=self.weights.weights,
                insights=[],
                theory_rows=self._theory_rows(rolls),
            )

        results = self._run_predictions(rolls)
        combined = self._combine(results)
        top5 = sorted(combined.items(), key=lambda item: item[1], reverse=True)[:5]
        ranges = {
            "2–6": sum(combined[total] for total in range(2, 7)) * 100.0,
            "7": combined[7] * 100.0,
            "8–12": sum(combined[total] for total in range(8, 13)) * 100.0,
        }
        return ForecastReport(
            enabled=True,
            roll_count=roll_count,
            message="Анализ активен.",
            top5=[(total, confidence * 100.0) for total, confidence in top5],
            range_probabilities=ranges,
            combined_scores=combined,
            analyzer_results=results,
            weights=self.weights.weights,
            insights=self._insights(rolls, results),
            theory_rows=self._theory_rows(rolls),
        )

    def ingest_new_roll(self, rolls: list[Roll]) -> ForecastReport:
        """Update weights for the newest roll and return a current report."""

        if len(rolls) < self._previous_len:
            return self.rebuild(rolls)
        if len(rolls) == self._previous_len:
            return self.report(rolls)
        if len(rolls) == self._previous_len + 1 and len(rolls) > MIN_ROLLS_FOR_ANALYSIS:
            self.weights.learn_from_actual(rolls[-1].total)
        self._previous_len = len(rolls)
        report = self.report(rolls)
        if report.enabled:
            self.weights.remember_predictions({name: result.scores for name, result in report.analyzer_results.items()})
        return report

    def _run_predictions(self, rolls: list[Roll]) -> dict[str, AnalyzerResult]:
        return {analyzer.name: analyzer.analyze(rolls) for analyzer in self.analyzers}

    def _combine(self, results: dict[str, AnalyzerResult]) -> dict[int, float]:
        weights = self.weights.weights
        combined = {total: 0.0 for total in SUMS}
        for name, result in results.items():
            weight = weights.get(name, 0.0)
            for total, score in result.scores.items():
                combined[total] += weight * score
        return normalize_scores(combined)

    @staticmethod
    def _theory_rows(rolls: list[Roll]) -> list[tuple[int, float, float, float]]:
        counts = Counter(roll.total for roll in rolls)
        total_count = max(1, len(rolls))
        rows = []
        for total in SUMS:
            theory = THEORETICAL_SUM_PROBS[total] * 100.0
            fact = counts[total] / total_count * 100.0 if rolls else 0.0
            rows.append((total, theory, fact, fact - theory))
        return rows

    def _insights(self, rolls: list[Roll], results: dict[str, AnalyzerResult]) -> list[str]:
        totals = [roll.total for roll in rolls]
        counts = Counter(totals)
        last20 = Counter(totals[-20:])
        insights: list[str] = []

        transitions = results.get("Переходы")
        if transitions:
            matrix = transitions.details.get("transitions", {})
            for source in (10, 8):
                counter = matrix.get(source) if isinstance(matrix, dict) else None
                if counter:
                    target, count = counter.most_common(1)[0]
                    insights.append(f"После {source} чаще всего выпадает {target} ({count} раз).")

        longest = self._longest_streak(totals)
        current = self._current_streak(totals)
        if longest:
            insights.append(f"Самая длинная серия: {longest[0]} — {longest[1]} подряд.")
        if current:
            insights.append(f"Текущая серия: {current[0]} — {current[1]} подряд.")

        hot = [str(total) for total, _ in last20.most_common(3)]
        cold = [str(total) for total, _ in sorted(((total, last20[total]) for total in SUMS), key=lambda item: (item[1], item[0]))[:3]]
        absent = sorted(self._absence(totals).items(), key=lambda item: item[1], reverse=True)[:3]
        insights.append(f"Самые горячие суммы за 20 бросков: {', '.join(hot) if hot else 'нет'}." )
        insights.append(f"Самые холодные суммы за 20 бросков: {', '.join(cold)}.")
        insights.append("Дольше всего отсутствуют: " + ", ".join(f"{total} ({gap})" for total, gap in absent) + ".")

        transition_counter = Counter(zip(totals, totals[1:], strict=False))
        if transition_counter:
            insights.append("Частые переходы: " + ", ".join(f"{a}→{b} ({c})" for (a, b), c in transition_counter.most_common(5)) + ".")
        pair_counter = Counter((roll.red, roll.blue) for roll in rolls)
        if pair_counter:
            insights.append("Частые комбинации: " + ", ".join(f"({r},{b}) ({c})" for (r, b), c in pair_counter.most_common(5)) + ".")
        return insights

    @staticmethod
    def _absence(totals: list[int]) -> dict[int, int]:
        gaps = {}
        for total in SUMS:
            try:
                gaps[total] = len(totals) - 1 - (len(totals) - 1 - totals[::-1].index(total))
            except ValueError:
                gaps[total] = len(totals)
        return gaps

    @staticmethod
    def _current_streak(totals: list[int]) -> tuple[str, int] | None:
        if not totals:
            return None
        last = totals[-1]
        length = 0
        for total in reversed(totals):
            if total == last:
                length += 1
            else:
                break
        return str(last), length

    @staticmethod
    def _longest_streak(totals: list[int]) -> tuple[str, int] | None:
        if not totals:
            return None
        best_value = totals[0]
        best_len = 1
        current_value = totals[0]
        current_len = 1
        for total in totals[1:]:
            if total == current_value:
                current_len += 1
            else:
                current_value = total
                current_len = 1
            if current_len > best_len:
                best_value = current_value
                best_len = current_len
        return str(best_value), best_len
