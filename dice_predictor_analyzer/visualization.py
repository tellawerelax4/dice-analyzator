"""Qt widgets for Rondo/Twist charts."""

from __future__ import annotations

from collections import Counter

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget

from .model import SUMS


class LineChart(QWidget):
    def __init__(self, title: str, minimum: float = 0.0, maximum: float = 1.0) -> None:
        super().__init__()
        self.title = title
        self.minimum = minimum
        self.maximum = maximum
        self.values: list[float] = []
        self.setMinimumHeight(130)

    def set_values(self, values: list[float], minimum: float | None = None, maximum: float | None = None) -> None:
        self.values = list(values)
        if minimum is not None:
            self.minimum = minimum
        if maximum is not None:
            self.maximum = maximum
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#111827"))
        painter.setPen(QColor("#cbd5e1"))
        painter.drawText(12, 22, self.title)
        area = QRectF(36, 34, self.width() - 54, self.height() - 52)
        painter.setPen(QPen(QColor("#334155"), 1))
        painter.drawRect(area)
        if len(self.values) < 2:
            return
        span = max(0.0001, self.maximum - self.minimum)
        points = []
        for index, value in enumerate(self.values):
            x = area.left() + index * area.width() / max(1, len(self.values) - 1)
            y = area.bottom() - ((value - self.minimum) / span) * area.height()
            points.append((x, y))
        painter.setPen(QPen(QColor("#38bdf8"), 2))
        for (x1, y1), (x2, y2) in zip(points, points[1:], strict=False):
            painter.drawLine(int(x1), int(y1), int(x2), int(y2))


class BarChart(QWidget):
    def __init__(self, title: str) -> None:
        super().__init__()
        self.title = title
        self.values: dict[int, float] = {total: 0.0 for total in SUMS}
        self.setMinimumHeight(150)

    def set_totals(self, totals: list[int]) -> None:
        counter = Counter(totals)
        denominator = max(1, len(totals))
        self.values = {total: counter[total] / denominator for total in SUMS}
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#111827"))
        painter.setPen(QColor("#cbd5e1"))
        painter.drawText(12, 22, self.title)
        area = QRectF(32, 36, self.width() - 48, self.height() - 60)
        max_value = max(self.values.values()) or 1.0
        bar_width = area.width() / len(self.values)
        for index, total in enumerate(SUMS):
            value = self.values[total]
            height = area.height() * value / max_value
            x = area.left() + index * bar_width + 2
            y = area.bottom() - height
            painter.fillRect(QRectF(x, y, bar_width - 4, height), QColor("#22c55e" if total == 7 else "#6366f1"))
            painter.setPen(QColor("#cbd5e1"))
            painter.drawText(QRectF(x, area.bottom() + 2, bar_width - 4, 18), Qt.AlignmentFlag.AlignCenter, str(total))


class WeightsChart(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.history: list[dict[str, float]] = []
        self.setMinimumHeight(160)

    def set_history(self, history: list[dict[str, float]]) -> None:
        self.history = history[-80:]
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#111827"))
        painter.setPen(QColor("#cbd5e1"))
        painter.drawText(12, 22, "График изменения весов алгоритмов")
        if len(self.history) < 2:
            return
        area = QRectF(36, 34, self.width() - 54, self.height() - 52)
        painter.setPen(QPen(QColor("#334155"), 1))
        painter.drawRect(area)
        names = list(self.history[-1].keys())
        colors = ["#38bdf8", "#f59e0b", "#22c55e", "#e879f9", "#f43f5e", "#a3e635"]
        for color, name in zip(colors, names, strict=False):
            points = []
            for index, row in enumerate(self.history):
                x = area.left() + index * area.width() / max(1, len(self.history) - 1)
                y = area.bottom() - row.get(name, 0.0) * area.height()
                points.append((x, y))
            painter.setPen(QPen(QColor(color), 2))
            for (x1, y1), (x2, y2) in zip(points, points[1:], strict=False):
                painter.drawLine(int(x1), int(y1), int(x2), int(y2))
