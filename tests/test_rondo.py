from datetime import datetime

from dice_predictor_analyzer.forecast import PredictionEngine
from dice_predictor_analyzer.parser import RondoParser, SelectorConfig, detect_new_results
from dice_predictor_analyzer.statistics import StatisticsEngine
from dice_predictor_analyzer.storage import ResultStorage


def config() -> SelectorConfig:
    return SelectorConfig("quickGame-frame", ["div"], 750, "debug_page.html", 300, "newest_first")


def test_parser_extracts_only_valid_sums_from_html():
    html = """
    <div class="sc-zOxLx hniCWV"><div><div class="sc-eXVaYZ kZFbzU">7</div></div></div>
    <div>12</div><div>1</div><div>13</div><span>10</span><div>Баланс 100</div>
    """
    assert RondoParser(config()).read_history_from_html(html) == [7, 12, 10]


def test_detect_new_results_handles_repeated_values_and_both_orders():
    assert detect_new_results([7, 7], [7, 7, 7]) == [7]
    assert detect_new_results([8, 7, 7], [7, 8, 7, 7]) == [7]
    assert detect_new_results([6, 8, 9], [6, 8, 9, 10, 10]) == [10, 10]


def test_storage_is_sum_only():
    storage = ResultStorage()
    storage.add_result(7, datetime.now())
    storage.add_result(12, datetime.now())
    assert storage.totals == [7, 12]
    assert storage.last_result == 12


def test_forecast_disabled_before_15_and_enabled_after():
    engine = PredictionEngine()
    short = [7] * 14
    disabled = engine.forecast(short)
    assert not disabled.enabled
    assert "Собрано 14 из 15" in disabled.message

    totals = [7, 8, 6, 9, 5, 10, 4, 11, 3, 12, 2, 7, 8, 6, 7]
    enabled = engine.forecast(totals)
    assert enabled.enabled
    assert len(enabled.top5) == 5
    assert round(sum(enabled.range_probs.values()), 6) == 1
    assert round(sum(enabled.parity_probs.values()), 6) == 1


def test_statistics_engine_top_hit_rates():
    stats = StatisticsEngine()
    stats.remember_forecast([(7, 0.3), (8, 0.2), (6, 0.1), (9, 0.08), (5, 0.07)], 0.5)
    stats.settle_actual(8)
    accuracy = stats.accuracy()
    assert accuracy["TOP-1"] == 0
    assert accuracy["TOP-3"] == 1
    assert accuracy["TOP-5"] == 1
    assert stats.log[0].actual == 8


def test_weights_change_after_actual_result():
    engine = PredictionEngine()
    totals = [7, 8, 6, 9, 5, 10, 4, 11, 3, 12, 2, 7, 8, 6, 7]
    before = engine.forecast(totals).weights
    engine.process_new_result(totals + [7], 7)
    after = engine.weights.weights
    assert before != after
