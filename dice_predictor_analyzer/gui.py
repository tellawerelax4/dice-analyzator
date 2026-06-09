"""PySide6 desktop interface for Dice Predictor Analyzer."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .forecast import ForecastEngine, ForecastReport
from .model import RollHistory
from .visualization import SumChartWidget


class DicePredictorWindow(QMainWindow):
    """Main game-time optimized application window."""

    def __init__(self) -> None:
        super().__init__()
        self.history = RollHistory()
        self.engine = ForecastEngine()
        self.pending_red: int | None = None
        self.pending_blue: int | None = None

        self.setWindowTitle("Dice Predictor Analyzer")
        self.resize(1320, 860)
        self._build_ui()
        self._apply_style()
        self._refresh(self.engine.report(list(self.history.rolls)))

    def _build_ui(self) -> None:
        root = QWidget()
        main_layout = QHBoxLayout(root)
        main_layout.setContentsMargins(14, 14, 14, 14)
        main_layout.setSpacing(14)
        main_layout.addWidget(self._build_left_panel(), 0)
        main_layout.addWidget(self._build_right_panel(), 1)
        self.setCentralWidget(root)

    def _build_left_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("leftPanel")
        layout = QVBoxLayout(panel)
        layout.setSpacing(12)

        title = QLabel("Ввод броска")
        title.setObjectName("sectionTitle")
        layout.addWidget(title)
        self.red_status = QLabel("Красный кубик: не выбран")
        self.blue_status = QLabel("Синий кубик: не выбран")
        layout.addWidget(self.red_status)
        layout.addWidget(self._dice_group("Красный кубик", "red"))
        layout.addWidget(self.blue_status)
        layout.addWidget(self._dice_group("Синий кубик", "blue"))

        history_title = QLabel("История бросков")
        history_title.setObjectName("sectionTitle")
        layout.addWidget(history_title)
        self.history_list = QListWidget()
        self.history_list.setMinimumWidth(310)
        self.history_list.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(self.history_list, 1)

        delete_button = QPushButton("Удалить последний бросок")
        delete_button.setObjectName("dangerButton")
        delete_button.clicked.connect(self._delete_last)
        layout.addWidget(delete_button)
        return panel

    def _dice_group(self, title: str, die: str) -> QGroupBox:
        group = QGroupBox(title)
        grid = QGridLayout(group)
        grid.setSpacing(8)
        for face in range(1, 7):
            button = QPushButton(str(face))
            button.setMinimumSize(78, 62)
            button.clicked.connect(lambda _checked=False, f=face, d=die: self._select_die(d, f))
            row = 0 if face <= 3 else 1
            col = (face - 1) % 3
            grid.addWidget(button, row, col)
        return group

    def _build_right_panel(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setSpacing(12)

        self.status_label = QLabel()
        self.status_label.setObjectName("statusLabel")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        self.top_label = QLabel("ТОП-5 рекомендуемых сумм")
        self.top_label.setObjectName("sectionTitle")
        layout.addWidget(self.top_label)
        self.top_text = QTextEdit()
        self.top_text.setReadOnly(True)
        self.top_text.setMaximumHeight(170)
        layout.addWidget(self.top_text)

        self.range_label = QLabel()
        self.range_label.setObjectName("rangeLabel")
        layout.addWidget(self.range_label)

        latest_title = QLabel("Последние суммы")
        latest_title.setObjectName("sectionTitle")
        layout.addWidget(latest_title)
        self.latest_label = QLabel("—")
        self.latest_label.setObjectName("latestLabel")
        self.latest_label.setWordWrap(True)
        layout.addWidget(self.latest_label)

        chart_title = QLabel("График последних 50 сумм")
        chart_title.setObjectName("sectionTitle")
        layout.addWidget(chart_title)
        self.chart = SumChartWidget()
        layout.addWidget(self.chart)

        analytics_title = QLabel("Аналитическая панель")
        analytics_title.setObjectName("sectionTitle")
        layout.addWidget(analytics_title)
        self.analytics_text = QTextEdit()
        self.analytics_text.setReadOnly(True)
        self.analytics_text.setMinimumHeight(220)
        layout.addWidget(self.analytics_text)

        theory_title = QLabel("Теоретическая и фактическая статистика сумм")
        theory_title.setObjectName("sectionTitle")
        layout.addWidget(theory_title)
        self.theory_table = QTableWidget(11, 4)
        self.theory_table.setHorizontalHeaderLabels(["Сумма", "Теория", "Факт", "Отклонение"])
        self.theory_table.verticalHeader().setVisible(False)
        self.theory_table.setMinimumHeight(370)
        layout.addWidget(self.theory_table)

        scroll.setWidget(content)
        return scroll

    def _select_die(self, die: str, face: int) -> None:
        if die == "red":
            self.pending_red = face
            self.red_status.setText(f"Красный кубик: {face}")
        else:
            self.pending_blue = face
            self.blue_status.setText(f"Синий кубик: {face}")
        if self.pending_red is not None and self.pending_blue is not None:
            self.history.add(self.pending_red, self.pending_blue)
            self.pending_red = None
            self.pending_blue = None
            self.red_status.setText("Красный кубик: не выбран")
            self.blue_status.setText("Синий кубик: не выбран")
            self._refresh(self.engine.ingest_new_roll(list(self.history.rolls)))

    def _delete_last(self) -> None:
        self.history.remove_last()
        self._refresh(self.engine.rebuild(list(self.history.rolls)))

    def _refresh(self, report: ForecastReport) -> None:
        rolls = list(self.history.rolls)
        self.history_list.clear()
        for index, roll in enumerate(rolls, start=1):
            self.history_list.addItem(roll.label(index))
        self.history_list.scrollToBottom()

        totals = [roll.total for roll in rolls]
        self.latest_label.setText(" ".join(str(total) for total in totals[-20:]) if totals else "—")
        self.chart.set_values(totals[-50:])
        self.status_label.setText(report.message)

        if not report.enabled:
            self.top_text.setPlainText(report.message)
            self.range_label.setText("2–6 → 0.00%     7 → 0.00%     8–12 → 0.00%")
            self.analytics_text.setPlainText("Аналитика включится автоматически после 15 бросков.")
        else:
            self.top_text.setPlainText("\n".join(
                f"{rank}. {total} — уверенность {confidence:.2f}%"
                for rank, (total, confidence) in enumerate(report.top5, start=1)
            ))
            ranges = report.range_probabilities
            self.range_label.setText(
                f"2–6 → {ranges['2–6']:.2f}%     7 → {ranges['7']:.2f}%     8–12 → {ranges['8–12']:.2f}%"
            )
            weights = "\n".join(f"{name}: {weight * 100:.1f}%" for name, weight in report.weights.items())
            self.analytics_text.setPlainText("\n".join(report.insights) + "\n\nТекущие веса алгоритмов:\n" + weights)
        self._fill_theory_table(report)

    def _fill_theory_table(self, report: ForecastReport) -> None:
        for row, (total, theory, fact, deviation) in enumerate(report.theory_rows):
            values = [str(total), f"{theory:.2f}%", f"{fact:.2f}%", f"{deviation:+.2f}%"]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.theory_table.setItem(row, column, item)
        self.theory_table.resizeColumnsToContents()

    def _apply_style(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow, QWidget { background: #0f172a; color: #e5e7eb; font-size: 18px; }
            #leftPanel, QGroupBox, QTextEdit, QListWidget, QTableWidget { background: #111827; border: 1px solid #334155; border-radius: 10px; }
            QPushButton { background: #2563eb; color: white; border: none; border-radius: 10px; font-size: 24px; font-weight: 700; padding: 12px; }
            QPushButton:hover { background: #1d4ed8; }
            #dangerButton { background: #dc2626; font-size: 20px; }
            #dangerButton:hover { background: #b91c1c; }
            QGroupBox { font-weight: 700; padding-top: 18px; margin-top: 8px; }
            QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 6px; }
            #sectionTitle { font-size: 24px; font-weight: 800; color: #facc15; }
            #statusLabel { font-size: 22px; font-weight: 800; color: #93c5fd; }
            #rangeLabel { font-size: 22px; font-weight: 800; color: #34d399; }
            #latestLabel { font-size: 24px; font-weight: 800; color: #f97316; }
            QHeaderView::section { background: #1f2937; color: #e5e7eb; padding: 6px; border: 1px solid #334155; }
            """
        )


def run_app() -> int:
    app = QApplication([])
    window = DicePredictorWindow()
    window.show()
    return app.exec()
