# Task 1 implementation report

Status: DONE. No commit: workspace has no Git repository. No dependency changes, UI changes, network calls, DataBundle persistence, or edits to existing core modules.

Implemented `DailyHkdResult` and `connect_daily_hkd` with row-level FX diagnostics, conservative same-month endpoint selection, inclusive 0–7 day age policy, strict unit confirmation, preserved blocked C1 results, and S03 `reconcile_hkd` computation through an in-memory total-return DataBundle. Every target price row remains present. Actual price and FX dates, endpoint ages/reasons, source file/sheet/row/hash evidence, policy metadata and preview-only historical flags are preserved. Malformed FX input raises for USD; for HKD its diagnostic error is retained in metadata while the fixed-one FX calculation remains independent.

Implemented `cached_daily_fx`: full snapshot verification and raw artifact reparsing; strict Yahoo HKD=X identity including Europe/London, close (not adjusted close), raw boolean rejection, manifest range filtering and explicit unofficial source name; HKMA ordered raw pages with hashes, HTTP status, offsets, page lengths, range/nonoverlap, completeness checks and deterministic combined hash plus ordered per-page hashes. Partial sources remain partial. Failed/unparseable final HTTP pages are rejected rather than silently converted to success. Reads are immutable.

## TDD evidence

RED log: `outputs/acceptance/S04C2/task-1-red.log`.

- `.venv/bin/python -m pytest tests/test_daily_hkd.py -q`: 26 failed before implementation. Expected assertions included `daily HKD connector is missing`; direct import tests reported missing module. These establish the absent public feature and numerical behavior.
- `.venv/bin/python -m pytest tests/test_fx_cache.py -q`: 13 failed before implementation, with the expected `daily FX cache reader missing` assertion. Cache module did not exist when run.
- `.venv/bin/python -m pytest tests/test_daily_hkd.py::test_hkd_remains_valid_despite_malformed_irrelevant_fx -q`: 1 failed with `ValueError: FX required columns missing`. Then adjusted HKD-only error handling and reran GREEN.

GREEN log: `outputs/acceptance/S04C2/task-1-green.log`.

Command: `.venv/bin/python -m pytest tests/test_daily_hkd.py tests/test_fx_cache.py tests/test_fx.py tests/test_daily_monthly.py -q`

Result: **79 passed, 2 warnings** (elapsed time see log). Both warnings are existing exchange_calendars XHKG/NumPy timedelta deprecations. New coverage includes hand calculation 100→110 and 7.8→7.9, 0/7/8-day policies, weekend endpoint, no cross-month fill, latest invalid values/duplicate rows/invalid dates/source/currency, older invalid diagnostic rows, strict confirmation, partial source, local blocking, HKD without or malformed FX, overflow, nonmutation and file provenance/JSON metadata. Fixed-fetch immutable snapshots cover Yahoo success/partial/identity/raw boolean/hash/unavailable and HKMA ordered success/partial/boolean/overlap/offset/completeness/HTTP failure.

Files created:

- `src/portfolio/data/daily_hkd.py`
- `src/portfolio/data/fx_cache.py`
- `tests/test_daily_hkd.py`
- `tests/test_fx_cache.py`

Self-review: formula is exclusively delegated to existing S03 code; all target rows and C1 reasons are retained; raw bytes are omitted from JSON metadata while their hash remains; source hashes and snapshot bytes are never rewritten. Existing regression modules pass. Additional post-GREEN tests confirmed weekend/no-carry-forward, older bad-row scope, and metadata evidence. These extra characterization tests passed immediately and are distinguished from the initial failing-first coverage above. No unresolved implementation concerns. Full application regression and UI integration are controller tasks.
