"""In-memory data model for two-dice rolls."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


MIN_SUM = 2
MAX_SUM = 12
DIE_FACES = range(1, 7)
SUMS = range(MIN_SUM, MAX_SUM + 1)
MIN_ROLLS_FOR_ANALYSIS = 15

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
THEORETICAL_DIE_PROB = 1.0 / 6.0


@dataclass(frozen=True, slots=True)
class Roll:
    """One completed physical roll of red and blue dice."""

    red: int
    blue: int

    def __post_init__(self) -> None:
        if self.red not in DIE_FACES or self.blue not in DIE_FACES:
            raise ValueError("Dice faces must be integers from 1 to 6.")

    @property
    def total(self) -> int:
        return self.red + self.blue

    def label(self, index: int) -> str:
        return f"#{index}  {self.red}+{self.blue}={self.total}"


class RollHistory:
    """Mutable, memory-only roll history."""

    def __init__(self, rolls: Iterable[Roll] | None = None) -> None:
        self._rolls: list[Roll] = list(rolls or [])

    @property
    def rolls(self) -> tuple[Roll, ...]:
        return tuple(self._rolls)

    @property
    def totals(self) -> list[int]:
        return [roll.total for roll in self._rolls]

    def __len__(self) -> int:
        return len(self._rolls)

    def add(self, red: int, blue: int) -> Roll:
        roll = Roll(red=red, blue=blue)
        self._rolls.append(roll)
        return roll

    def remove_last(self) -> Roll | None:
        if not self._rolls:
            return None
        return self._rolls.pop()

    def clear(self) -> None:
        self._rolls.clear()
