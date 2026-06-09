"""Independent statistical analyzers used by the adaptive ensemble."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections import Counter, defaultdict
from dataclasses import dataclass

from .model import DIE_FACES, SUMS, Roll, THEORETICAL_DIE_PROB, THEORETICAL_SUM_PROBS
from .utils import min_max_scale, normalize_scores


@dataclass(frozen=True, slots=True)
class AnalyzerResult:
    """Prediction scores for one independent analyzer."""

    name: str
    scores: dict[int, float]
    details: dict[str, object]


class BaseAnalyzer(ABC):
    """Contract for independent next-sum analyzers."""

    name: str

    @abstractmethod
    def analyze(self, rolls: list[Roll]) -> AnalyzerResult:
        """Analyze complete history and return normalized sum scores."""


class FrequencyAnalyzer(BaseAnalyzer):
    name = "Частоты"

    def analyze(self, rolls: list[Roll]) -> AnalyzerResult:
        total_count = max(1, len(rolls))
        sum_counts = Counter(roll.total for roll in rolls)
        red_counts = Counter(roll.red for roll in rolls)
        blue_counts = Counter(roll.blue for roll in rolls)
        pair_counts = Counter((roll.red, roll.blue) for roll in rolls)

        scores: dict[int, float] = {}
        for total in SUMS:
            sum_component = sum_counts[total] / total_count
            face_component = 0.0
            combo_component = 0.0
            valid_pairs = [(red, total - red) for red in DIE_FACES if total - red in DIE_FACES]
            for red, blue in valid_pairs:
                face_component += (red_counts[red] / total_count) * (blue_counts[blue] / total_count)
                combo_component += pair_counts[(red, blue)] / total_count
            scores[total] = 0.55 * sum_component + 0.25 * face_component + 0.20 * combo_component

        return AnalyzerResult(
            self.name,
            normalize_scores(scores),
            {"sum_counts": sum_counts, "red_counts": red_counts, "blue_counts": blue_counts, "pair_counts": pair_counts},
        )


class RecencyAnalyzer(BaseAnalyzer):
    name = "Давность"

    def analyze(self, rolls: list[Roll]) -> AnalyzerResult:
        totals = [roll.total for roll in rolls]
        gaps: dict[int, int] = {}
        for total in SUMS:
            try:
                last_index = len(totals) - 1 - totals[::-1].index(total)
                gaps[total] = len(totals) - 1 - last_index
            except ValueError:
                gaps[total] = len(totals)
        scaled = min_max_scale(gaps)
        scores = {total: 0.15 + scaled[total] for total in SUMS}
        return AnalyzerResult(self.name, normalize_scores(scores), {"gaps": gaps})


class TransitionAnalyzer(BaseAnalyzer):
    name = "Переходы"

    def analyze(self, rolls: list[Roll]) -> AnalyzerResult:
        transitions: dict[int, Counter[int]] = {total: Counter() for total in SUMS}
        totals = [roll.total for roll in rolls]
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

    def analyze(self, rolls: list[Roll]) -> AnalyzerResult:
        totals = [roll.total for roll in rolls]
        global_counts = Counter(totals)
        last10 = Counter(totals[-10:])
        last20 = Counter(totals[-20:])
        global_den = max(1, len(totals))
        den10 = max(1, min(10, len(totals)))
        den20 = max(1, min(20, len(totals)))
        scores = {}
        for total in SUMS:
            global_rate = global_counts[total] / global_den
            local10_rate = last10[total] / den10
            local20_rate = last20[total] / den20
            acceleration = max(0.0, local10_rate - global_rate) + max(0.0, local20_rate - global_rate)
            scores[total] = 0.35 * global_rate + 0.40 * local10_rate + 0.25 * local20_rate + 0.35 * acceleration
        return AnalyzerResult(self.name, normalize_scores(scores), {"last10": last10, "last20": last20})


class StreakAnalyzer(BaseAnalyzer):
    name = "Серии"

    @staticmethod
    def _range_name(total: int) -> str:
        if total <= 6:
            return "2–6"
        if total == 7:
            return "7"
        return "8–12"

    def analyze(self, rolls: list[Roll]) -> AnalyzerResult:
        totals = [roll.total for roll in rolls]
        if not totals:
            return AnalyzerResult(self.name, normalize_scores({}), {})

        last = totals[-1]
        same_len = 0
        for total in reversed(totals):
            if total == last:
                same_len += 1
            else:
                break

        parity = last % 2
        parity_len = 0
        for total in reversed(totals):
            if total % 2 == parity:
                parity_len += 1
            else:
                break

        range_name = self._range_name(last)
        range_len = 0
        for total in reversed(totals):
            if self._range_name(total) == range_name:
                range_len += 1
            else:
                break

        scores = {total: 1.0 for total in SUMS}
        if same_len >= 2:
            scores[last] += min(4.0, same_len * 0.8)
        if parity_len >= 3:
            for total in SUMS:
                if total % 2 == parity:
                    scores[total] += min(3.0, parity_len * 0.35)
        if range_len >= 3:
            for total in SUMS:
                if self._range_name(total) == range_name:
                    scores[total] += min(3.0, range_len * 0.35)

        return AnalyzerResult(
            self.name,
            normalize_scores(scores),
            {"same_len": same_len, "parity_len": parity_len, "range_len": range_len, "range_name": range_name},
        )


class BiasAnalyzer(BaseAnalyzer):
    name = "Перекос"

    def analyze(self, rolls: list[Roll]) -> AnalyzerResult:
        total_count = max(1, len(rolls))
        red_counts = Counter(roll.red for roll in rolls)
        blue_counts = Counter(roll.blue for roll in rolls)
        sum_counts = Counter(roll.total for roll in rolls)

        sum_deviation = {
            total: (sum_counts[total] / total_count) - THEORETICAL_SUM_PROBS[total]
            for total in SUMS
        }
        red_deviation = {face: (red_counts[face] / total_count) - THEORETICAL_DIE_PROB for face in DIE_FACES}
        blue_deviation = {face: (blue_counts[face] / total_count) - THEORETICAL_DIE_PROB for face in DIE_FACES}

        scores: dict[int, float] = {}
        for total in SUMS:
            valid_pairs = [(red, total - red) for red in DIE_FACES if total - red in DIE_FACES]
            face_bias = sum(max(0.0, red_deviation[red]) + max(0.0, blue_deviation[blue]) for red, blue in valid_pairs)
            scores[total] = max(0.0, THEORETICAL_SUM_PROBS[total] + max(0.0, sum_deviation[total]) + face_bias / 6.0)
        return AnalyzerResult(
            self.name,
            normalize_scores(scores),
            {"sum_deviation": sum_deviation, "red_deviation": red_deviation, "blue_deviation": blue_deviation},
        )


class CombinationAnalyzer(BaseAnalyzer):
    name = "Комбинации"

    def analyze(self, rolls: list[Roll]) -> AnalyzerResult:
        pair_counts = Counter((roll.red, roll.blue) for roll in rolls)
        scores = defaultdict(float)
        for (red, blue), count in pair_counts.items():
            scores[red + blue] += count
        if rolls:
            last_pair = (rolls[-1].red, rolls[-1].blue)
            reverse_pair = (rolls[-1].blue, rolls[-1].red)
            scores[sum(last_pair)] += pair_counts[last_pair] * 0.3 + pair_counts[reverse_pair] * 0.2
        return AnalyzerResult(self.name, normalize_scores(scores), {"pair_counts": pair_counts})


def create_default_analyzers() -> list[BaseAnalyzer]:
    """Return all independent algorithms in ensemble order."""

    return [
        FrequencyAnalyzer(),
        RecencyAnalyzer(),
        TransitionAnalyzer(),
        LocalTrendAnalyzer(),
        StreakAnalyzer(),
        BiasAnalyzer(),
        CombinationAnalyzer(),
    ]
