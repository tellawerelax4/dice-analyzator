"""Qt widgets for compact dice-sum visualization."""

from __future__ import annotations

try:
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtGui import QColor, QPainter, QPen
    from PySide6.QtWidgets import QWidget
except ImportError:  # pragma: no cover - allows headless unit tests without Qt installed
    QPointF = Qt = QColor = QPainter = QPen = QWidget = None  # type: ignore[assignment]


if QWidget is not None:

    class SumChartWidget(QWidget):
        """Simple auto-updating line chart for the last 50 sums."""

        def __init__(self, parent=None) -> None:
            super().__init__(parent)
            self._values: list[int] = []
            self.setMinimumHeight(180)

        def set_values(self, values: list[int]) -> None:
            self._values = values[-50:]
            self.update()

        def paintEvent(self, event) -> None:  # noqa: N802 - Qt API name
            super().paintEvent(event)
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            rect = self.rect().adjusted(12, 12, -12, -24)
            painter.fillRect(self.rect(), QColor("#111827"))
            painter.setPen(QPen(QColor("#374151"), 1))
            for step in range(2, 13, 2):
                y = rect.bottom() - (step - 2) / 10 * rect.height()
                painter.drawLine(rect.left(), int(y), rect.right(), int(y))
                painter.drawText(2, int(y) + 4, str(step))
            if len(self._values) < 2:
                painter.setPen(QColor("#d1d5db"))
                painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "График появится после 2 бросков")
                return
            points = []
            for index, value in enumerate(self._values):
                x = rect.left() + index / max(1, len(self._values) - 1) * rect.width()
                y = rect.bottom() - (value - 2) / 10 * rect.height()
                points.append(QPointF(x, y))
            painter.setPen(QPen(QColor("#38bdf8"), 3))
            for start, end in zip(points, points[1:], strict=False):
                painter.drawLine(start, end)
            painter.setBrush(QColor("#f97316"))
            painter.setPen(Qt.PenStyle.NoPen)
            for point in points:
                painter.drawEllipse(point, 4, 4)
else:

    class SumChartWidget:  # type: ignore[no-redef]
        """Fallback placeholder when Qt is unavailable."""

        def __init__(self, *args, **kwargs) -> None:
            self._values: list[int] = []

        def set_values(self, values: list[int]) -> None:
            self._values = values[-50:]
