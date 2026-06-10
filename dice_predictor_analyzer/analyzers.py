"""Independent sum-only analytics for the adaptive ensemble."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections import Counter, defaultdict
from dataclasses import dataclass

from .model import SUMS, THEORETICAL_SUM_PROBS
from .utils import min_max_scale, normalize_scores


@dataclass(frozen=True, slots=True)
class AnalyzerResult:
    name: str
    scores: dict[int, float]
    details: dict[str, object]


class BaseAnalyzer(ABC):
    name: str

    @abstractmethod
    def analyze(self, totals: list[int]) -> AnalyzerResult:
        """Return a normalized rating for sums 2..12."""


class FrequencyAnalyzer(BaseAnalyzer):
    name = "Частоты"

    def analyze(self, totals: list[int]) -> AnalyzerResult:
        counts = Counter(totals)
        denominator = max(1, len(totals))
        scores = {total: counts[total] / denominator for total in SUMS}
        deviations = {total: scores[total] - THEORETICAL_SUM_PROBS[total] for total in SUMS}
        return AnalyzerResult(self.name, normalize_scores(scores), {"counts": counts, "deviations": deviations})


class RecencyAnalyzer(BaseAnalyzer):
    name = "Давность"

    def analyze(self, totals: list[int]) -> AnalyzerResult:
        gaps = absence_map(totals)
        scaled = min_max_scale(gaps)
        scores = {total: 0.1 + scaled[total] for total in SUMS}
        return AnalyzerResult(self.name, normalize_scores(scores), {"gaps": gaps})


class TransitionAnalyzer(BaseAnalyzer):
    name = "Переходы"

    def analyze(self, totals: list[int]) -> AnalyzerResult:
        transitions: dict[int, Counter[int]] = {total: Counter() for total in SUMS}
        for previous, current in zip(totals, totals[1:], strict=False):
            transitions[previous][current] += 1
        if not totals:
            return AnalyzerResult(self.name, normalize_scores({}), {"transitions": transitions})
        current_total = totals[-1]
        current_transitions = transitions[current_total]
        if current_transitions:
            scores = {total: current_transitions[total] for total in SUMS}
        else:
            global_next = Counter(totals[1:])
            scores = {total: global_next[total] for total in SUMS}
        return AnalyzerResult(self.name, normalize_scores(scores), {"transitions": transitions})


class LocalTrendAnalyzer(BaseAnalyzer):
    name = "Локальные тренды"

    def analyze(self, totals: list[int]) -> AnalyzerResult:
        global_counts = Counter(totals)
        windows = {10: Counter(totals[-10:]), 20: Counter(totals[-20:]), 50: Counter(totals[-50:])}
        global_den = max(1, len(totals))
        scores: dict[int, float] = {}
        for total in SUMS:
            global_rate = global_counts[total] / global_den
            local_score = 0.0
            for size, counter in windows.items():
                denominator = max(1, min(size, len(totals)))
                local_rate = counter[total] / denominator
                local_score += local_rate + max(0.0, local_rate - global_rate)
            scores[total] = 0.25 * global_rate + 0.75 * (local_score / 3)
        return AnalyzerResult(self.name, normalize_scores(scores), {"windows": windows})


class StreakAnalyzer(BaseAnalyzer):
    name = "Серии"

    def analyze(self, totals: list[int]) -> AnalyzerResult:
        if not totals:
            return AnalyzerResult(self.name, normalize_scores({}), {})
        same_value, same_len = current_same_streak(totals)
        parity_name, parity_len = current_parity_streak(totals)
        range_name, range_len = current_range_streak(totals)

        scores = {total: 1.0 for total in SUMS}
        if same_len >= 2:
            scores[same_value] += min(4.0, same_len * 0.75)
        if parity_len >= 3:
            wanted_parity = 0 if parity_name == "чётные" else 1
            for total in SUMS:
                if total % 2 == wanted_parity:
                    scores[total] += min(2.5, parity_len * 0.25)
        if range_len >= 3:
            for total in SUMS:
                if range_label(total) == range_name:
                    scores[total] += min(3.0, range_len * 0.3)
        return AnalyzerResult(
            self.name,
            normalize_scores(scores),
            {
                "same": (str(same_value), same_len),
                "parity": (parity_name, parity_len),
                "range": (range_name, range_len),
                "longest_same": longest_same_streak(totals),
            },
        )


class DistributionBiasAnalyzer(BaseAnalyzer):
    name = "Перекос распределения"

    def analyze(self, totals: list[int]) -> AnalyzerResult:
        counts = Counter(totals)
        denominator = max(1, len(totals))
        deviations = {total: counts[total] / denominator - THEORETICAL_SUM_PROBS[total] for total in SUMS}
        positive = {total: max(0.0, deviations[total]) for total in SUMS}
        if sum(positive.values()) <= 0:
            positive = {total: THEORETICAL_SUM_PROBS[total] for total in SUMS}
        return AnalyzerResult(self.name, normalize_scores(positive), {"deviations": deviations})


def absence_map(totals: list[int]) -> dict[int, int]:
    gaps: dict[int, int] = {}
    for total in SUMS:
        try:
            last_index = len(totals) - 1 - totals[::-1].index(total)
            gaps[total] = len(totals) - 1 - last_index
        except ValueError:
            gaps[total] = len(totals)
    return gaps


def range_label(total: int) -> str:
    if total <= 6:
        return "2-6"
    if total == 7:
        return "7"
    return "8-12"


def current_same_streak(totals: list[int]) -> tuple[int, int]:
    last = totals[-1]
    length = 0
    for total in reversed(totals):
        if total == last:
            length += 1
        else:
            break
    return last, length


def current_parity_streak(totals: list[int]) -> tuple[str, int]:
    parity = totals[-1] % 2
    length = 0
    for total in reversed(totals):
        if total % 2 == parity:
            length += 1
        else:
            break
    return ("чётные" if parity == 0 else "нечётные"), length


def current_range_streak(totals: list[int]) -> tuple[str, int]:
    label = range_label(totals[-1])
    length = 0
    for total in reversed(totals):
        if range_label(total) == label:
            length += 1
        else:
            break
    return label, length


def longest_same_streak(totals: list[int]) -> tuple[str, int] | None:
    if not totals:
        return None
    best_value = current_value = totals[0]
    best_len = current_len = 1
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
