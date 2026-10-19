"""Independent arithmetic and input checks for the offline S00 demo."""

import os
from pathlib import Path
import subprocess
import sys

import numpy as np
import pandas as pd
import pytest


def test_hand_calculated_buy_and_hold():
    from portfolio.demo import buy_and_hold

    result = buy_and_hold([100, 110, 120], initial_cash=1000)
    np.testing.assert_allclose(result["units"], [10, 10, 10])
    np.testing.assert_allclose(result["value_hkd"], [1000, 1100, 1200])
    np.testing.assert_allclose(result["period_return"], [0, 0.1, 120 / 110 - 1])
    np.testing.assert_allclose(result["cumulative_return"], [0, 0.1, 0.2])


def test_fractional_units_and_loss_are_not_hidden():
    from portfolio.demo import buy_and_hold

    result = buy_and_hold([80, 100, 60], initial_cash=100)
    np.testing.assert_allclose(result["units"], [1.25, 1.25, 1.25])
    np.testing.assert_allclose(result["value_hkd"], [100, 125, 75])
    assert result["cumulative_return"].iloc[-1] == pytest.approx(-0.25)


@pytest.mark.parametrize("prices", [[], [100], [100, 0], [100, -1], [100, np.nan], [100, np.inf], [[100, 110], [120, 130]]])
def test_invalid_prices_are_rejected(prices):
    from portfolio.demo import buy_and_hold

    with pytest.raises(ValueError, match="prices"):
        buy_and_hold(prices, initial_cash=1000)


@pytest.mark.parametrize("cash", [0, -100, np.nan, np.inf])
def test_invalid_capital_is_rejected(cash):
    from portfolio.demo import buy_and_hold

    with pytest.raises(ValueError, match="initial_cash"):
        buy_and_hold([100, 110], initial_cash=cash)


def test_command_line_export_is_reproducible(tmp_path):
    project_root = Path(__file__).resolve().parents[1]
    # Exercise the installed entry point without pytest's source-path setting.
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    paths = [tmp_path / "first" / "sample.csv", tmp_path / "second" / "sample.csv"]
    for output in paths:
        completed = subprocess.run(
            [sys.executable, "-m", "portfolio.demo", "--output", str(output)],
            cwd=project_root, env=env, capture_output=True, text=True, timeout=90,
        )
        assert completed.returncode == 0, completed.stderr
        assert "1200.00 HKD" in completed.stdout
        assert "20.00%" in completed.stdout
    assert paths[0].read_bytes() == paths[1].read_bytes()
    rows = pd.read_csv(paths[0])
    assert len(rows) == 3
    assert rows["value_hkd"].iloc[-1] == pytest.approx(1200)
    assert rows["cumulative_return"].iloc[-1] == pytest.approx(0.2)
