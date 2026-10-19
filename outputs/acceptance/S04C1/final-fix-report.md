# S04-C1 final boolean-price fix

The immutable-cache raw boundary now rejects any JSON boolean adjusted-price entry before the shared Yahoo parser can coerce it to 1/0. No shared provider or snapshot interfaces changed. Both True and False endpoint regressions use complete December 2024/January 2025 trading sessions and otherwise valid OHLC/volume arrays. They archive the exact HTTP raw bytes and verify all snapshot files remain unchanged after rejection. No result is returned and no invalid row is silently dropped.

Changed files:
- src/portfolio/data/monthly_cache.py
- tests/test_daily_monthly.py
- outputs/acceptance/S04C1/final-fix-red.log
- outputs/acceptance/S04C1/final-fix-green.log
- outputs/acceptance/S04C1/final-fix-report.md

Exact RED command:
```sh
.venv/bin/python -m pytest tests/test_daily_monthly.py -k raw_boolean_adjusted_endpoint -q > outputs/acceptance/S04C1/final-fix-red.log 2>&1; cat outputs/acceptance/S04C1/final-fix-red.log
```
Both tests failed with DID NOT RAISE ValueError before production changes (pytest exit 1; the log-display shell command exits 0).

Exact GREEN command:
```sh
.venv/bin/python -m pytest tests/test_daily_monthly.py tests/test_daily_monthly_verification.py tests/test_updates.py -q > outputs/acceptance/S04C1/final-fix-green.log 2>&1; cat outputs/acceptance/S04C1/final-fix-green.log
```
54 passed; two existing exchange_calendars NumPy deprecation warnings. Pytest exited 0.

Exact RED then GREEN output:
```text
FF                                                                       [100%]
=================================== FAILURES ===================================
_______ test_readonly_cache_rejects_raw_boolean_adjusted_endpoint[True] ________

tmp_path = PosixPath('/private/var/folders/_2/5m_w643956j04bn0h0mb6gn80000gn/T/pytest-of-jackliang/pytest-151/test_readonly_cache_rejects_ra0')
boolean_price = True

    @pytest.mark.parametrize('boolean_price', [True, False])
    def test_readonly_cache_rejects_raw_boolean_adjusted_endpoint(tmp_path, boolean_price):
        from portfolio.data.monthly_cache import cached_monthly_prices
        from portfolio.data.updates import run_update
        from portfolio.data.providers.base import RawResponse
        from portfolio.data.snapshots import MANIFEST
        days = sample()
        adjusted = list(days.adj_close)
        adjusted[-1] = boolean_price
        payload = {'chart': {'error': None, 'result': [{
            'meta': {'symbol': 'SPY', 'currency': 'USD', 'instrumentType': 'ETF',
                     'exchangeTimezoneName': 'America/New_York'},
            'timestamp': [int(pd.Timestamp(d, tz='America/New_York').timestamp()) for d in days.date],
            'indicators': {
                'quote': [{**{k: list(days.adj_close) for k in ['open', 'high', 'low', 'close']},
                           'volume': [1] * len(days)}],
                'adjclose': [{'adjclose': adjusted}],
            },
        }]}}
        raw = json.dumps(payload).encode()
        run = run_update(tmp_path, ['SPY'], '2024-12-01', '2025-02-01',
                         fetch=lambda *a: RawResponse(raw, 200))
        folder = tmp_path / 'runs' / run
        manifest = json.loads((folder / MANIFEST).read_text())
        assert (folder / manifest['items'][0]['raw_file']).read_bytes() == raw
        before = {p.name: p.read_bytes() for p in folder.iterdir()}
>       with pytest.raises(ValueError, match='boolean adjusted price'):
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       Failed: DID NOT RAISE ValueError

tests/test_daily_monthly.py:116: Failed
_______ test_readonly_cache_rejects_raw_boolean_adjusted_endpoint[False] _______

tmp_path = PosixPath('/private/var/folders/_2/5m_w643956j04bn0h0mb6gn80000gn/T/pytest-of-jackliang/pytest-151/test_readonly_cache_rejects_ra1')
boolean_price = False

    @pytest.mark.parametrize('boolean_price', [True, False])
    def test_readonly_cache_rejects_raw_boolean_adjusted_endpoint(tmp_path, boolean_price):
        from portfolio.data.monthly_cache import cached_monthly_prices
        from portfolio.data.updates import run_update
        from portfolio.data.providers.base import RawResponse
        from portfolio.data.snapshots import MANIFEST
        days = sample()
        adjusted = list(days.adj_close)
        adjusted[-1] = boolean_price
        payload = {'chart': {'error': None, 'result': [{
            'meta': {'symbol': 'SPY', 'currency': 'USD', 'instrumentType': 'ETF',
                     'exchangeTimezoneName': 'America/New_York'},
            'timestamp': [int(pd.Timestamp(d, tz='America/New_York').timestamp()) for d in days.date],
            'indicators': {
                'quote': [{**{k: list(days.adj_close) for k in ['open', 'high', 'low', 'close']},
                           'volume': [1] * len(days)}],
                'adjclose': [{'adjclose': adjusted}],
            },
        }]}}
        raw = json.dumps(payload).encode()
        run = run_update(tmp_path, ['SPY'], '2024-12-01', '2025-02-01',
                         fetch=lambda *a: RawResponse(raw, 200))
        folder = tmp_path / 'runs' / run
        manifest = json.loads((folder / MANIFEST).read_text())
        assert (folder / manifest['items'][0]['raw_file']).read_bytes() == raw
        before = {p.name: p.read_bytes() for p in folder.iterdir()}
>       with pytest.raises(ValueError, match='boolean adjusted price'):
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       Failed: DID NOT RAISE ValueError

tests/test_daily_monthly.py:116: Failed
=========================== short test summary info ============================
FAILED tests/test_daily_monthly.py::test_readonly_cache_rejects_raw_boolean_adjusted_endpoint[True]
FAILED tests/test_daily_monthly.py::test_readonly_cache_rejects_raw_boolean_adjusted_endpoint[False]
2 failed, 18 deselected in 0.87s
......................................................                   [100%]
=============================== warnings summary ===============================
tests/test_daily_monthly.py::test_calendar_official_dates_and_dst
tests/test_daily_monthly.py::test_calendar_official_dates_and_dst
  /Users/jackliang/Desktop/CityU/5052_Investment/Assignment/Group/.venv/lib/python3.14/site-packages/exchange_calendars/exchange_calendar_xhkg.py:363: DeprecationWarning: The 'generic' unit for NumPy timedelta is deprecated, and will raise an error in the future. This includes implicit conversion of bare integers (e.g. `+ 1`). Please use a specific unit instead.
    easter_monday = EasterMonday.dates(years[0], years[-1] + 1)

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
54 passed, 2 warnings in 0.88s

```

