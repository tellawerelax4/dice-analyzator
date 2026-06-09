# Dice Predictor Analyzer

Desktop Python 3.12+ application for analyzing a history of two physical six-sided dice rolls and building an adaptive ensemble forecast for the next sum.

## Run

```bash
python -m dice_predictor_analyzer
```

Install `PySide6` first if it is not already available:

```bash
python -m pip install -e .
```

## Notes

The app stores roll history only in memory. Forecasting activates after 15 rolls.
