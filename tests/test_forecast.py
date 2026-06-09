from dice_predictor_analyzer.forecast import ForecastEngine
from dice_predictor_analyzer.model import MIN_ROLLS_FOR_ANALYSIS, Roll


def sample_rolls(count=20):
    pattern = [(1, 1), (3, 4), (5, 3), (6, 4), (2, 5), (6, 6), (4, 4), (1, 6)]
    return [Roll(*pattern[index % len(pattern)]) for index in range(count)]


def test_forecast_disabled_before_minimum():
    report = ForecastEngine().report(sample_rolls(MIN_ROLLS_FOR_ANALYSIS - 1))

    assert not report.enabled
    assert "Недостаточно данных" in report.message


def test_forecast_enabled_and_ranges_sum_to_100():
    report = ForecastEngine().rebuild(sample_rolls(25))

    assert report.enabled
    assert len(report.top5) == 5
    assert set(report.range_probabilities) == {"2–6", "7", "8–12"}
    assert sum(report.range_probabilities.values()) == pytest_approx_100()
    assert abs(sum(report.weights.values()) - 1.0) < 1e-9


def pytest_approx_100():
    import pytest

    return pytest.approx(100.0, abs=1e-7)


def test_weights_change_after_learning():
    engine = ForecastEngine()
    report = engine.rebuild(sample_rolls(35))

    weights = report.weights
    assert len({round(value, 4) for value in weights.values()}) > 1


def test_delete_rebuild_handles_shorter_history():
    engine = ForecastEngine()
    rolls = sample_rolls(18)
    full_report = engine.rebuild(rolls)
    shorter_report = engine.rebuild(rolls[:-5])

    assert full_report.enabled
    assert not shorter_report.enabled
