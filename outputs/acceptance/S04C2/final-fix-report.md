# S04-C2 final review fixes

Status: DONE. All four confirmed Important findings reproduced and repaired. Scope extension for finding 4 (monthly cache boundary + reusable provider helper) was explicitly authorized by the controller. No Git, installs, network calls, service restarts or raw-cache mutations were performed.

## Findings and mechanisms

1. Unknown FX dates: RED reproduced missing rejection for null, boolean, NaN and string NaT timestamps in an otherwise positive, two-month success-labelled snapshot. Infinity and malformed text were already rejected. New `validated_timestamp_rows` checks the complete original timestamp array before parsing/filtering: numeric, nonboolean, finite, representable, nonmissing and unique. Both cache readers call this helper; the public FX cache raises ValueError before any unlocatable row can disappear.
2. Original FX source rows: RED showed the reversed raw response produced [1,2] instead of [2,1]. The helper returns original timestamp-to-one-based-ordinal mapping; FX cache uses the parser's retained timestamp_utc to recover raw JSON row numbers after sort/filter. Regression checks dates, values, selected endpoint row numbers and unchanged stored bytes.
3. Independent auditor: RED showed empty/short/extra FX endpoints, empty/extra/wrong-date reconciliation rows, wrong final FX dates/ages/quotes escaped detection (empty reconciliation raised the wrong exception). Auditor now requires exactly one January 2025 reconciliation and two unique exact natural month labels; endpoint comparison uses date keys rather than truncating zip. Both reconciliation FX observed dates and ages are compared independently, as are its actual fx_start/fx_end values (native HKD requires 1; blocked USD requires missing). Parameterized tests also cover duplicate/wrong-date endpoints, missing age and wrong quote, which existing checks already caught. Direct raw JSON reference construction remains independent of all production selection functions. Existing full, missing-month and invalid-latest diagnostic cases still agree honestly.
4. Unknown price dates: added real complete December/January SPY-session raw response with an extra null timestamp and positive OHLC/adjusted-close/volume. Upstream audit genuinely reports success; RED showed cached_monthly_prices silently dropped the null row. Shared timestamp helper now rejects at this boundary before date filtering. Snapshot bytes stay unchanged. Existing parse_yahoo_chart and audit_price implementations were left unchanged; price provenance logic was not broadened.

## RED evidence

` .venv/bin/python -m pytest tests/test_fx_cache.py tests/test_daily_hkd_verification.py -q `

Before production changes: **17 failed, 24 passed, 2 existing warnings**. Failures were missing rejection, wrong ordinals and overlooked evidence tampering; several defensive cases already passed as noted above.

` .venv/bin/python -m pytest tests/test_daily_monthly.py::test_cache_rejects_unlocatable_raw_price_before_filter -q `

Before monthly-cache fix: **1 failed** (DID NOT RAISE ValueError); upstream success assertion passed.

Both outputs: `final-fix-red.txt` (second command appended).

## GREEN evidence

Initial three-finding covering command:

` .venv/bin/python -m pytest tests/test_fx_cache.py tests/test_daily_hkd.py tests/test_daily_hkd_verification.py tests/test_daily_hkd_view.py -q `

**83 passed, 2 existing warnings** before controller's finding-4 extension.

Final extended covering command after the last source change:

` .venv/bin/python -m pytest tests/test_fx_cache.py tests/test_daily_hkd.py tests/test_daily_hkd_verification.py tests/test_daily_hkd_view.py tests/test_daily_monthly.py tests/test_updates.py -q `

**133 passed, 2 warnings in 4.46s**; output `final-fix-green.txt`. Warnings are unchanged XHKG/NumPy timedelta deprecations, not suppressed. No complete suite was rerun.

## Actual legacy CLI replay

` .venv/bin/python scripts/verify_daily_hkd.py --s01-manifest outputs/acceptance/S01/snapshots/20261012T143920Z-6f4d426f/snapshot_manifest.json --output outputs/acceptance/S04C2/legacy_replay `

Completed after final source change, with both all_comparisons_agree and all_hkd_previews_valid true. Regenerated reconciliation, metadata, endpoint/observation CSVs and independent reference/report in legacy_replay/. Stdout: `final-fix-replay.txt`. Preserved global partial status and historical_eligible=false. SPY direct HKD return 0.030586128808627544; 2800.HK 0.010869455644421322.

## Changed code and tests

- src/portfolio/data/fx_cache.py
- src/portfolio/data/monthly_cache.py
- src/portfolio/data/providers/yahoo.py (new boundary helper only)
- scripts/verify_daily_hkd.py
- tests/test_fx_cache.py
- tests/test_daily_monthly.py
- tests/test_daily_hkd_verification.py

Self-review: checked boundary validation occurs before filters, map ordinals reflect raw arrays, timestamp duplicates remain rejected, cardinality guards precede iloc/record access, independent references still read raw JSON, missing-FX diagnostics remain accepted, native HKD quotes remain fixed at 1, and partial-cache rules/formulas remain unchanged. No unresolved fix concerns. Controller retains final re-review/full-suite/reinstall/browser responsibilities.

## Re-review Minor: oversized integer timestamp

Confirmed that `math.isfinite(10**400)` raised OverflowError before the helper's conversion guard. Added `10**400` to the existing invalid-timestamp parameter cases first.

RED: `.venv/bin/python -m pytest tests/test_fx_cache.py -k unknown_timestamp -q` — **1 failed, 6 passed, 14 deselected**; oversized integer raised OverflowError instead of the expected ValueError. Evidence: `final-fix-minor-red.txt`.

Fix: moved the existing raw timestamp checks inside the same try/except that converts conversion errors (including OverflowError) to ValueError. Only changed providers/yahoo.py and the existing test parameter list.

GREEN: `.venv/bin/python -m pytest tests/test_fx_cache.py tests/test_daily_monthly.py tests/test_daily_hkd_verification.py -q` — **63 passed, 2 existing calendar warnings in 1.42s**. Evidence: `final-fix-minor-green.txt`. No full suite, reinstall, restart, or other source changes. Self-review confirms all helper checks now use the intended public ValueError contract. Prior replay artifacts remain from the preceding final-fix source version; no financial selection behavior changed in this narrow robustness fix.
