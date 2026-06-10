"""Selenium collector for Bettery Rondo/Twist DOM history."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from pathlib import Path

from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from .parser import RondoParser, SelectorConfig, detect_new_results

BETTERY_RONDO_URL = "https://bettery.ru/quick-games/game_rondo"
LOGGER = logging.getLogger(__name__)

StatusCallback = Callable[[str], None]
ResultsCallback = Callable[[list[int]], None]


class SeleniumCollector:
    """Owns Selenium WebDriver and polls the iframe history as source of truth."""

    def __init__(
        self,
        config: SelectorConfig,
        url: str = BETTERY_RONDO_URL,
        headless: bool = False,
        status_callback: StatusCallback | None = None,
        results_callback: ResultsCallback | None = None,
    ) -> None:
        self.config = config
        self.parser = RondoParser(config)
        self.url = url
        self.headless = headless
        self.status_callback = status_callback
        self.results_callback = results_callback
        self.driver: WebDriver | None = None
        self.previous_snapshot: list[int] = []
        self.running = False

    def start_driver(self) -> None:
        options = ChromeOptions()
        if self.headless:
            options.add_argument("--headless=new")
        options.add_argument("--disable-notifications")
        options.add_argument("--window-size=1280,900")
        self.driver = webdriver.Chrome(options=options)
        self._status("Браузер Selenium запущен")

    def run_diagnostics(self) -> list[int]:
        """Open site, switch to iframe, save HTML, log latest found results."""
        driver = self._driver()
        self._status(f"Открываю {self.url}")
        driver.get(self.url)
        try:
            WebDriverWait(driver, 25).until(EC.presence_of_element_located((By.ID, self.config.iframe_id)))
            iframe = driver.find_element(By.ID, self.config.iframe_id)
            driver.switch_to.frame(iframe)
            self._status(f"Iframe найден: #{self.config.iframe_id}")
        except WebDriverException as exc:
            self._save_debug_html(driver.page_source)
            message = f"Не удалось найти iframe #{self.config.iframe_id}: {exc}"
            LOGGER.exception(message)
            self._status(message)
            return []

        time.sleep(2.0)
        snapshot = self.parser.read_history_from_driver(driver)
        self._save_debug_html(driver.page_source)
        if snapshot:
            LOGGER.info("Найдено результатов: %s; последние: %s", len(snapshot), snapshot[-20:])
            self._status(f"Диагностика: найдено результатов {len(snapshot)}; последние {snapshot[-10:]}")
        else:
            self._status("История результатов не найдена. HTML сохранён в debug_page.html; проверьте selectors.json")
            LOGGER.warning("История не найдена; HTML сохранён для диагностики")
        self.previous_snapshot = snapshot
        return snapshot

    def poll_forever(self) -> None:
        """Poll full history snapshots every 500-1000 ms until stopped."""
        if self.driver is None:
            self.start_driver()
        initial = self.run_diagnostics()
        if initial and self.results_callback:
            self.results_callback(self._to_chronological(initial))
        self.running = True
        interval = max(500, min(1000, self.config.poll_interval_ms)) / 1000.0
        while self.running:
            try:
                driver = self._driver()
                current = self.parser.read_history_from_driver(driver)
                new_results = detect_new_results(self.previous_snapshot, current)
                if new_results:
                    self.previous_snapshot = current
                    self._status(f"Новые результаты: {new_results}")
                    if self.results_callback:
                        self.results_callback(self._to_chronological(new_results))
                elif current and current != self.previous_snapshot:
                    self.previous_snapshot = current
                time.sleep(interval)
            except WebDriverException as exc:
                self._status(f"Ошибка Selenium/DOM: {exc}")
                LOGGER.exception("Selenium polling error")
                time.sleep(2.0)

    def stop(self) -> None:
        self.running = False
        if self.driver is not None:
            self.driver.quit()
            self.driver = None
            self._status("Selenium остановлен")

    def _to_chronological(self, results: list[int]) -> list[int]:
        if self.config.history_order == "newest_first":
            return list(reversed(results))
        return list(results)

    def _driver(self) -> WebDriver:
        if self.driver is None:
            raise RuntimeError("Selenium WebDriver is not started.")
        return self.driver

    def _save_debug_html(self, html: str) -> None:
        Path(self.config.debug_html_path).write_text(html, encoding="utf-8")

    def _status(self, message: str) -> None:
        LOGGER.info(message)
        if self.status_callback:
            self.status_callback(message)
