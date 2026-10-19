"""Offline S00 buy-and-hold example, with prices already denominated in HKD.

Periods are synthetic observations, not calendar dates. Fractional units are
allowed. This verifies the environment only; it is not a formal portfolio.
"""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import vectorbt as vbt


def buy_and_hold(prices, *, initial_cash=1000.0):
    """Buy at the first observation and hold, with no fees or slippage.

    Returns a table of vectorbt values alongside holding units and returns.
    The first period's return is zero: its value is the initial observation.
    """
    prices = np.asarray(prices, dtype=float)
    if prices.ndim != 1 or len(prices) < 2:
        raise ValueError("prices must be a one-dimensional series with at least two observations")
    if not np.isfinite(prices).all() or (prices <= 0).any():
        raise ValueError("prices must be finite and strictly positive")
    initial_cash = float(initial_cash)
    if not np.isfinite(initial_cash) or initial_cash <= 0:
        raise ValueError("initial_cash must be finite and strictly positive")

    close = pd.Series(prices, name="synthetic_hkd_price")
    portfolio = vbt.Portfolio.from_holding(
        close, init_cash=initial_cash, fees=0.0, fixed_fees=0.0, slippage=0.0,
    )
    value = portfolio.value()
    return pd.DataFrame({
        "period": np.arange(len(prices)),
        "price_hkd": prices,
        "units": portfolio.assets().to_numpy(),
        "value_hkd": value.to_numpy(),
        "period_return": value.pct_change().fillna(0).to_numpy(),
        "cumulative_return": (value / initial_cash - 1).to_numpy(),
    })


def main():
    parser = argparse.ArgumentParser(description="Run the offline S00 HKD buy-and-hold example")
    parser.add_argument(
        "--output", type=Path,
        default=Path("outputs/acceptance/S00/smoke_result.csv"),
        help="CSV output path, relative to the current directory unless absolute",
    )
    args = parser.parse_args()
    result = buy_and_hold([100, 110, 120], initial_cash=1000)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(args.output, index=False, float_format="%.12f", lineterminator="\n")
    print("S00: synthetic HKD prices 100 -> 110 -> 120; initial capital 1000.00 HKD")
    print(f"Final value: {result['value_hkd'].iloc[-1]:.2f} HKD")
    print(f"Cumulative return: {result['cumulative_return'].iloc[-1]:.2%}")
    print(f"CSV: {args.output}")


if __name__ == "__main__":
    main()
