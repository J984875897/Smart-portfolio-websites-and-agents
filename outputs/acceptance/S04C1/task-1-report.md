# Task 1 report

Implemented pinned XNYS/XHKG calendar schedules, conservative daily completeness diagnostics, month-end price previews, and read-only Yahoo schema1 cache reparsing. Original-currency returns use a temporary DataBundle and the existing build_local_returns formula. All target months remain visible when blocked. No historical eligibility or availability timestamp is inferred.

Owned files: trading_calendar.py, daily_monthly.py, monthly_cache.py, test_daily_monthly.py, pyproject.toml, requirements.lock.txt. Existing dependency versions and existing contracts/providers/snapshots remain unchanged. No Git operations or network requests.

TDD evidence:

- `.venv/bin/python -m pytest tests/test_daily_monthly.py -q`: initial RED, 16 failed because locally imported feature modules did not exist; `task-1-red.log`.
- Initial implementation run caught a test fixture assigning infinity into a pandas integer column. Changed fixture prices to floating point, preserving the invalid-price behavior check.
- Added strict ISO as_of regression before tightening validation: RED 1 failed / 15 passed, `task-1-red-asof.log`.
- Same focused command final GREEN: 16 passed, `task-1-green.log`.
- `.venv/bin/python -m pytest tests/test_returns.py tests/test_updates.py tests/test_daily_monthly.py -q`: 62 passed, `task-1-regression.log`.

Coverage includes independent official-date/half-day/DST assertions, known 100/110 endpoint ratio, confirmation, missing anchor/end/midmonth, duplicates, weekends, nonfinite prices, invalid dates, empty frames, maturity boundaries, input preservation/reordering, offline operation, cache hashes/identity/partial/unavailable, and unchanged cache bytes. Cache diagnostics come from reparsed raw JSON rather than trusting derived CSV.

Self-review: all requested month labels are natural month ends; complete month checks include the preceding anchor month; missing final dates never fall back. Full-file snapshot verification precedes raw evidence use, and manifest request bounds filter reparsed observations. Calendar mapping/version, currency/source, blank available_at and false historical_eligible accompany returns. Cache metadata preserves the manifest and download timestamp separately.

Concern: pinned exchange_calendars 4.13.2 emits two upstream NumPy generic-timedelta DeprecationWarnings when constructing XHKG. Tests pass; no warning suppression added. Calendars are market proxies and preview checks do not certify security-specific suspensions, inception, or historical availability. Parent owns UI, independent verification, and full-suite acceptance.

## Review fixes

Added two regression tests before fixes. Finite positive endpoints 1e-308 and 1e308 now retain the shared calculator's blocked/invalid_value result when division overflows. Nonunique input column names now raise ValueError before DataFrame record conversion can discard conflicting values.

Exact command for both runs: `.venv/bin/python -m pytest tests/test_daily_monthly.py tests/test_returns.py -q` (stdout/stderr captured respectively in `task-1-review-red.log` and `task-1-review-green.log`).

RED output: `2 failed, 33 passed, 3 warnings in 0.75s`. Both added tests failed for the reported defects; the third warning was duplicate-column record conversion.

GREEN output: `35 passed, 2 warnings in 0.60s`. The remaining warnings are the already recorded upstream XHKG NumPy deprecations; no global suppression was added.
