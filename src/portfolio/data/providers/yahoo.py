"""Yahoo public chart transport and shared S01 field checks."""
from __future__ import annotations
import math
from datetime import datetime, timezone
from urllib.parse import quote
import numpy as np
import pandas as pd
from .base import RawResponse

def validated_timestamp_rows(payload: dict) -> dict:
    """Validate every raw timestamp before cache filtering; retain JSON ordinals."""
    results = payload.get('chart', {}).get('result') or []
    stamps = (results[0].get('timestamp') or []) if results else []
    try:
        if not stamps or any(isinstance(stamp, bool) or not isinstance(stamp, (int, float)) or not math.isfinite(stamp) for stamp in stamps):
            raise ValueError('Yahoo invalid timestamp')
        dates = pd.to_datetime(stamps, unit='s', utc=True)
    except (ValueError, TypeError, OverflowError) as error:
        raise ValueError('Yahoo invalid timestamp') from error
    if dates.isna().any() or dates.duplicated().any():
        raise ValueError('Yahoo invalid timestamp')
    return {stamp: index for index, stamp in enumerate(stamps, 1)}


def parse_yahoo_chart(payload: dict) -> tuple[pd.DataFrame, dict]:
    chart = payload.get("chart", {})
    if chart.get("error") or not chart.get("result"):
        raise ValueError("Yahoo chart error or no result")
    result = chart["result"][0]
    meta = result.get("meta", {})
    stamps = result.get("timestamp") or []
    if not stamps or not meta.get("exchangeTimezoneName"):
        raise ValueError("Yahoo timestamps/timezone missing")
    dates = pd.to_datetime(stamps, unit="s", utc=True).tz_convert(meta["exchangeTimezoneName"])
    indicators = result.get("indicators", {})
    quotes = indicators.get("quote", [{}])[0]
    values = {"date":dates.strftime("%Y-%m-%d"), "timestamp_utc":stamps}
    for field in ("open", "high", "low", "close", "volume"):
        column = quotes.get(field, [None] * len(stamps))
        if len(column) != len(stamps):
            raise ValueError("Yahoo field length changed")
        values[field] = pd.to_numeric(column, errors="raise")
    adjusted = indicators.get("adjclose", [{}])[0].get("adjclose", [None] * len(stamps))
    if len(adjusted) != len(stamps):
        raise ValueError("Yahoo adjusted field length changed")
    values["adj_close"] = pd.to_numeric(adjusted, errors="raise")
    table = pd.DataFrame(values)
    if table["date"].duplicated().any():
        raise ValueError("Yahoo duplicate daily date")
    for event, column in (("dividends", "dividends"), ("splits", "stock_splits"), ("capitalGains", "capital_gains")):
        mapped = {}
        for item in result.get("events", {}).get(event, {}).values():
            event_date = pd.Timestamp(item["date"], unit="s", tz="UTC").tz_convert(meta["exchangeTimezoneName"]).strftime("%Y-%m-%d")
            amount = float(item["numerator"]) / float(item["denominator"]) if event == "splits" else float(item["amount"])
            if not math.isfinite(amount) or (event == "splits" and amount <= 0):
                raise ValueError("Yahoo invalid action")
            mapped[event_date] = amount
        table[column] = table["date"].map(mapped).fillna(0.0)
    return table.sort_values("date").reset_index(drop=True), meta


def audit_price(table: pd.DataFrame, meta: dict, currency: str, provider_type: str, *, symbol=None, start=None, end=None) -> dict:
    if meta.get("currency") != currency or meta.get("instrumentType") != provider_type or (symbol is not None and meta.get("symbol") != symbol):
        return {"status":"unavailable", "reason":"currency_or_instrument_mismatch"}
    required = ["close"] if provider_type == "CURRENCY" else ["open", "high", "low", "close", "adj_close"]
    if table.empty:
        return {"status":"unavailable", "reason":"empty_prices"}
    valid = np.isfinite(table[required]).all(axis=1) & (table[required] > 0).all(axis=1)
    if provider_type != "CURRENCY":
        valid &= np.isfinite(table["volume"]) & (table["volume"] >= 0)
    periods = pd.PeriodIndex(pd.to_datetime(table.loc[valid, "date"]), freq="M")
    expected = pd.period_range(pd.Period(start,freq="M"),pd.Period(pd.Timestamp(end)-pd.Timedelta(days=1),freq="M"),freq="M") if start and end else (pd.period_range(periods.min(),periods.max(),freq="M") if len(periods) else pd.PeriodIndex([],freq="M"))
    gap_count = len(expected.difference(periods.unique()))
    success = valid.all() and len(table) >= 2 and not gap_count
    return {"status":"success" if success else "partial", "reason":"fields_verified" if success else "missing_invalid_prices_or_months", "rows":len(table), "valid_rows":int(valid.sum()), "first_date":table["date"].min(), "last_date":table["date"].max(), "observed_months":len(periods.unique()), "missing_months":gap_count, "dividend_events":int((table["dividends"] != 0).sum()), "split_events":int((table["stock_splits"] != 0).sum()), "capital_gain_events":int((table["capital_gains"] != 0).sum()), "quality_scope":"S01 field probe; NOT candidate eligibility", "daily_calendar_audit":"not_performed_S03"}


# Identities are the six S01 samples, using the S02 classification vocabulary.
CATALOG = {
    'AAPL': dict(name='Apple',tool_type='stock',asset_class='equity',exchange='NASDAQ',currency='USD',provider_type='EQUITY'),
    '0700.HK': dict(name='Tencent',tool_type='stock',asset_class='equity',exchange='HKEX',currency='HKD',provider_type='EQUITY'),
    'SPY': dict(name='SPDR S&P 500 ETF Trust',tool_type='ETF',asset_class='equity',exchange='NYSE Arca',currency='USD',provider_type='ETF'),
    '2800.HK': dict(name='Tracker Fund of Hong Kong',tool_type='ETF',asset_class='equity',exchange='HKEX',currency='HKD',provider_type='ETF'),
    'AGG': dict(name='iShares Core US Aggregate Bond ETF',tool_type='ETF',asset_class='bond',exchange='NYSE Arca',currency='USD',provider_type='ETF'),
    'GLD': dict(name='SPDR Gold Shares',tool_type='gold_trust',asset_class='commodity',exchange='NYSE Arca',currency='USD',provider_type='ETF'),
    'HKD=X': dict(name='USD/HKD',tool_type='fx',asset_class='currency',exchange='Yahoo',currency='HKD',provider_type='CURRENCY'),
}
for _symbol, _identity in CATALOG.items():
    _identity.update(ticker=_symbol, symbol=_symbol)


def fetch_yahoo(symbol: str, start: str, end: str, timeout: float) -> RawResponse:
    """Make exactly one public chart request; no history/login/crumb calls."""
    import yfinance  # Required local dynamic library initialization.
    from curl_cffi import requests
    params = dict(period1=int(datetime.fromisoformat(start).replace(tzinfo=timezone.utc).timestamp()),
                  period2=int(datetime.fromisoformat(end).replace(tzinfo=timezone.utc).timestamp()),
                  interval='1d', events='div,splits,capitalGains', includeAdjustedClose='true')
    response = requests.get('https://query1.finance.yahoo.com/v8/finance/chart/'+quote(symbol,safe=''),
                            params=params, timeout=timeout, impersonate='chrome', allow_redirects=False)
    return RawResponse(response.content, response.status_code)
