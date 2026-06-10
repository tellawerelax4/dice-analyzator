"""Memory-only storage for collected Rondo/Twist sums."""

from __future__ import annotations

from datetime import datetime

from .model import RollRecord


class ResultStorage:
    """Append-only in-memory result storage; nothing is persisted on exit."""

    def __init__(self) -> None:
        self._records: list[RollRecord] = []

    @property
    def records(self) -> tuple[RollRecord, ...]:
        return tuple(self._records)

    @property
    def totals(self) -> list[int]:
        return [record.total for record in self._records]

    @property
    def last_result(self) -> int | None:
        return self._records[-1].total if self._records else None

    def __len__(self) -> int:
        return len(self._records)

    def add_result(self, total: int, created_at: datetime | None = None) -> RollRecord:
        record = RollRecord(total=total, created_at=created_at or datetime.now())
        self._records.append(record)
        return record

    def clear(self) -> None:
        self._records.clear()
