"""PySide6 dark desktop interface for Bettery Rondo/Twist analyzer."""

from __future__ import annotations

import logging

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QApplication,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .collector import SeleniumCollector
from .forecast import Forecast, PredictionEngine
from .parser import SelectorConfig
from .statistics import StatisticsEngine
from .storage import ResultStorage
from .utils import pct
from .visualization import BarChart, LineChart, WeightsChart

LOGGER = logging.getLogger(__name__)


class CollectorThread(QThread):
    status_changed = Signal(str)
    results_found = Signal(list)
    failed = Signal(str)

    def __init__(self, config: SelectorConfig) -> None:
        super().__init__()
        self.config = config
        self.collector: SeleniumCollector | None = None

    def run(self) -> None:
        self.collector = SeleniumCollector(
            self.config,
            status_callback=self.status_changed.emit,
            results_callback=self.results_found.emit,
        )
        try:
            self.collector.poll_forever()
        except Exception as exc:  # noqa: BLE001 - GUI must show clear error instead of crashing.
            LOGGER.exception("Collector failed")
            self.failed.emit(str(exc))

    def stop(self) -> None:
        if self.collector is not None:
            self.collector.stop()
        self.quit()
        self.wait(3000)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Dice Predictor Analyzer — Bettery Rondo/Twist")
        self.resize(1500, 950)
        self.config = SelectorConfig.load()
        self.storage = ResultStorage()
        self.statistics = StatisticsEngine()
        self.engine = PredictionEngine(self.statistics)
        self.collector_thread: CollectorThread | None = None
        self._build_ui()
        self._apply_style()
        self._refresh(self.engine.forecast(self.storage.totals))

    def _build_ui(self) -> None:
        root = QWidget()
        self.setCentralWidget(root)
        layout = QHBoxLayout(root)
        splitter = QSplitter()
        layout.addWidget(splitter)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        self.connection_label = QLabel("Подключение: не запущено")
        self.parser_label = QLabel("Парсер: ожидание")
        self.count_label = QLabel("Бросков собрано: 0")
        self.last_label = QLabel("Последний результат: —")
        for label in [self.connection_label, self.parser_label, self.count_label, self.last_label]:
            label.setObjectName("statusLabel")
            left_layout.addWidget(label)

        buttons = QHBoxLayout()
        self.start_button = QPushButton("Запустить Selenium сбор")
        self.stop_button = QPushButton("Остановить")
        self.stop_button.setEnabled(False)
        self.start_button.clicked.connect(self.start_collection)
        self.stop_button.clicked.connect(self.stop_collection)
        buttons.addWidget(self.start_button)
        buttons.addWidget(self.stop_button)
        left_layout.addLayout(buttons)

        self.history_list = QListWidget()
        history_box = self._box("История результатов из DOM", self.history_list)
        left_layout.addWidget(history_box, 1)
        self.log_list = QListWidget()
        left_layout.addWidget(self._box("Статус/диагностика", self.log_list), 1)

        right = QWidget()
        right_layout = QGridLayout(right)
        self.top_label = QLabel()
        self.signal_bar = QProgressBar()
        self.signal_bar.setRange(0, 100)
        self.range_label = QLabel()
        self.parity_label = QLabel()
        self.hot_label = QLabel()
        self.cold_label = QLabel()
        self.absent_label = QLabel()
        self.weights_label = QLabel()
        self.accuracy_label = QLabel()
        self.insights_label = QLabel()
        for label in [self.top_label, self.range_label, self.parity_label, self.hot_label, self.cold_label, self.absent_label, self.weights_label, self.accuracy_label, self.insights_label]:
            label.setWordWrap(True)

        metrics_layout = QVBoxLayout()
        for title, widget in [
            ("ТОП-5 прогнозов", self.top_label),
            ("Сила сигнала", self.signal_bar),
            ("Диапазоны", self.range_label),
            ("Чётное / нечётное", self.parity_label),
            ("Горячие числа", self.hot_label),
            ("Холодные числа", self.cold_label),
            ("Отсутствующие числа", self.absent_label),
            ("Текущие веса", self.weights_label),
            ("Статистика точности", self.accuracy_label),
            ("Аналитика", self.insights_label),
        ]:
            metrics_layout.addWidget(self._box(title, widget))
        right_layout.addLayout(metrics_layout, 0, 0, 2, 1)

        self.results_chart = LineChart("График последних 50 результатов", minimum=2, maximum=12)
        self.signal_chart = LineChart("График силы сигнала", minimum=0, maximum=1)
        self.weights_chart = WeightsChart()
        self.distribution_chart = BarChart("Фактическое распределение сумм")
        charts_layout = QVBoxLayout()
        for chart in [self.results_chart, self.signal_chart, self.weights_chart, self.distribution_chart]:
            charts_layout.addWidget(chart)
        right_layout.addLayout(charts_layout, 0, 1)

        self.journal = QListWidget()
        self.theory_table = QTableWidget(11, 5)
        self.theory_table.setHorizontalHeaderLabels(["Сумма", "Теория", "Факт", "Отклонение", "Кол-во"])
        right_layout.addWidget(self._box("Журнал прогнозов (последние 100)", self.journal), 1, 1)
        right_layout.addWidget(self._box("Теория / факт / отклонение", self.theory_table), 2, 0, 1, 2)

        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setSizes([420, 1080])

    def start_collection(self) -> None:
        if self.collector_thread is not None:
            return
        self.collector_thread = CollectorThread(self.config)
        self.collector_thread.status_changed.connect(self._on_status)
        self.collector_thread.results_found.connect(self._on_results)
        self.collector_thread.failed.connect(self._on_failed)
        self.collector_thread.start()
        self.connection_label.setText("Подключение: запускается")
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)

    def stop_collection(self) -> None:
        if self.collector_thread is not None:
            self.collector_thread.stop()
            self.collector_thread = None
        self.connection_label.setText("Подключение: остановлено")
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)

    def closeEvent(self, event) -> None:  # noqa: N802
        self.stop_collection()
        super().closeEvent(event)

    def _on_status(self, message: str) -> None:
        self.parser_label.setText(f"Парсер: {message}")
        self.log_list.insertItem(0, message)
        while self.log_list.count() > 100:
            self.log_list.takeItem(self.log_list.count() - 1)

    def _on_failed(self, message: str) -> None:
        self._on_status(f"Ошибка: {message}")
        QMessageBox.warning(self, "Ошибка сбора", message)
        self.stop_collection()

    def _on_results(self, results: list[int]) -> None:
        for result in results:
            self.storage.add_result(int(result))
            forecast = self.engine.process_new_result(self.storage.totals, int(result))
        self.connection_label.setText("Подключение: активно")
        self._refresh(forecast if results else self.engine.forecast(self.storage.totals))

    def _refresh(self, forecast: Forecast) -> None:
        totals = self.storage.totals
        self.count_label.setText(f"Бросков собрано: {len(totals)}")
        self.last_label.setText(f"Последний результат: {self.storage.last_result if self.storage.last_result is not None else '—'}")
        self.history_list.clear()
        for index, record in enumerate(self.storage.records[-250:], start=max(1, len(self.storage.records) - 249)):
            self.history_list.addItem(record.label(index))

        if forecast.enabled:
            self.top_label.setText("\n".join(f"{index}. {total} — {pct(score)}" for index, (total, score) in enumerate(forecast.top5, start=1)))
        else:
            self.top_label.setText(forecast.message)
        self.signal_bar.setValue(round(forecast.signal_strength * 100))
        self.signal_bar.setFormat(f"СИЛА СИГНАЛА: {forecast.signal_strength * 100:.0f}%")
        self.range_label.setText("\n".join(f"{name}: {pct(value)}" for name, value in forecast.range_probs.items()))
        self.parity_label.setText("\n".join(f"{name}: {pct(value)}" for name, value in forecast.parity_probs.items()))
        self.hot_label.setText(", ".join(f"{total} ({count})" for total, count in forecast.hot) or "—")
        self.cold_label.setText(", ".join(f"{total} ({count})" for total, count in forecast.cold) or "—")
        self.absent_label.setText("\n".join(f"{total} — отсутствует {gap} бросков" for total, gap in forecast.absent))
        self.weights_label.setText("\n".join(f"{name}: {pct(weight)}" for name, weight in forecast.weights.items()))
        self.accuracy_label.setText("\n".join(f"{name}: {pct(value)}" for name, value in self.statistics.accuracy().items()))
        self.insights_label.setText("\n".join(forecast.insights))

        self.journal.clear()
        for item in self.statistics.log:
            top = ", ".join(f"{total}:{score * 100:.0f}%" for total, score in item.top5)
            self.journal.addItem(f"{item.created_at:%H:%M:%S} | {top} | сигнал {item.confidence * 100:.0f}% | факт {item.actual}")

        for row, (total, theory, fact, deviation, count) in enumerate(forecast.theory_rows):
            for column, value in enumerate([str(total), pct(theory), pct(fact), f"{deviation * 100:+.2f}%", str(count)]):
                self.theory_table.setItem(row, column, QTableWidgetItem(value))
        self.results_chart.set_values([float(value) for value in totals[-50:]], minimum=2, maximum=12)
        self.signal_chart.set_values(self.engine.signal_history, minimum=0, maximum=1)
        self.weights_chart.set_history(self.engine.weights.history)
        self.distribution_chart.set_totals(totals)

    @staticmethod
    def _box(title: str, widget: QWidget) -> QGroupBox:
        box = QGroupBox(title)
        layout = QVBoxLayout(box)
        layout.addWidget(widget)
        return box

    def _apply_style(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow, QWidget { background: #0f172a; color: #e5e7eb; font-size: 15px; }
            QGroupBox { border: 1px solid #334155; border-radius: 8px; margin-top: 10px; padding: 10px; font-weight: 700; }
            QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 6px; color: #93c5fd; }
            QLabel#statusLabel { font-size: 18px; font-weight: 700; padding: 8px; background: #111827; border-radius: 8px; }
            QPushButton { background: #2563eb; color: white; border: none; border-radius: 8px; padding: 12px; font-size: 16px; font-weight: 700; }
            QPushButton:disabled { background: #475569; color: #94a3b8; }
            QListWidget, QTableWidget { background: #111827; border: 1px solid #334155; border-radius: 6px; }
            QProgressBar { border: 1px solid #334155; border-radius: 8px; text-align: center; height: 30px; background: #111827; }
            QProgressBar::chunk { background: #22c55e; border-radius: 8px; }
            """
        )


def run_app() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    app = QApplication([])
    window = MainWindow()
    window.show()
    return app.exec()
