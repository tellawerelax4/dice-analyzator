"""Configurable DOM parsing for Bettery Rondo/Twist result history."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver

from .model import SUMS

DEFAULT_SELECTORS: dict[str, Any] = {
    "iframe_id": "quickGame-frame",
    "poll_interval_ms": 750,
    "debug_html_path": "debug_page.html",
    "result_selectors": [
        "[data-testid*='history' i] div",
        "[class*='history' i] div",
        "[class*='History'] div",
        ".sc-eXVaYZ",
        "div",
    ],
    "max_results": 300,
    "history_order": "newest_first",
}


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.tokens: list[str] = []

    def handle_data(self, data: str) -> None:
        cleaned = data.strip()
        if cleaned:
            self.tokens.append(cleaned)


@dataclass(slots=True)
class SelectorConfig:
    """Selectors that can be changed in selectors.json without code edits."""

    iframe_id: str
    result_selectors: list[str]
    poll_interval_ms: int
    debug_html_path: str
    max_results: int
    history_order: str

    @classmethod
    def load(cls, path: str | Path = "selectors.json") -> "SelectorConfig":
        config_path = Path(path)
        if not config_path.exists():
            config_path.write_text(json.dumps(DEFAULT_SELECTORS, ensure_ascii=False, indent=2), encoding="utf-8")
            data = DEFAULT_SELECTORS
        else:
            data = DEFAULT_SELECTORS | json.loads(config_path.read_text(encoding="utf-8"))
        return cls(
            iframe_id=str(data["iframe_id"]),
            result_selectors=list(data["result_selectors"]),
            poll_interval_ms=int(data.get("poll_interval_ms", 750)),
            debug_html_path=str(data.get("debug_html_path", "debug_page.html")),
            max_results=int(data.get("max_results", 300)),
            history_order=str(data.get("history_order", "newest_first")),
        )


class RondoParser:
    """Extracts valid sums (2..12) from Selenium DOM elements or saved HTML."""

    _number_pattern = re.compile(r"^\s*(?:[2-9]|10|11|12)\s*$")

    def __init__(self, config: SelectorConfig) -> None:
        self.config = config

    def read_history_from_driver(self, driver: WebDriver) -> list[int]:
        """Try configured CSS selectors and return the first non-empty result list."""
        for selector in self.config.result_selectors:
            elements = driver.find_elements(By.CSS_SELECTOR, selector)
            values = [self._parse_text(element.text) for element in elements]
            results = [value for value in values if value is not None]
            if results:
                return results[: self.config.max_results]
        return []

    def read_history_from_html(self, html: str) -> list[int]:
        """Diagnostic fallback used for tests and saved debug HTML inspection."""
        extractor = _TextExtractor()
        extractor.feed(html)
        results = [value for token in extractor.tokens if (value := self._parse_text(token)) is not None]
        return results[: self.config.max_results]

    @classmethod
    def _parse_text(cls, text: str) -> int | None:
        if cls._number_pattern.match(text):
            value = int(text.strip())
            if value in SUMS:
                return value
        return None


def detect_new_results(previous: list[int], current: list[int]) -> list[int]:
    """Detect newly appeared DOM history entries by comparing full snapshots.

    Supports both common orders: oldest-first append and newest-first prepended
    histories. This is why three identical visible results (7, 7, 7) are still
    handled by snapshot length/order comparison instead of comparing only the
    latest number.
    """
    if not current or current == previous:
        return []
    if not previous:
        return list(current)

    if current[: len(previous)] == previous:
        return current[len(previous) :]
    if current[-len(previous) :] == previous:
        return current[: -len(previous)]

    if len(current) == len(previous) and len(current) > 1:
        if current[1:] == previous[:-1]:
            return [current[0]]
        if current[:-1] == previous[1:]:
            return [current[-1]]

    best_prefix = 0
    limit = min(len(previous), len(current))
    for size in range(limit, 0, -1):
        if previous[-size:] == current[:size]:
            best_prefix = size
            break
    if best_prefix:
        return current[best_prefix:]

    best_suffix = 0
    for size in range(limit, 0, -1):
        if previous[:size] == current[-size:]:
            best_suffix = size
            break
    if best_suffix:
        return current[: len(current) - best_suffix]

    return current if len(current) > len(previous) else []
