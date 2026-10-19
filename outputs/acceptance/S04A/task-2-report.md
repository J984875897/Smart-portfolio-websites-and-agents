# Task 2 implementation report

Status: DONE. No Git repository initialized and no commit created.

## Implementation

- Added native Streamlit “下载与缓存” sidebar page; original default remains 数据导入. No new CSS or global font override.
- Added seven-symbol selection, default SPY/2800.HK, 2025-01-01 inclusive to 2025-02-01 exclusive, timeout 15 within 1–30 seconds. Preparing/cancelling a plan, parameter changes, navigation, cache opening, and exports never invoke transport. Parameter fingerprint invalidates a prepared plan. Explicit start performs the only update call.
- Plan previews item identities and exact request count, with pre-start cancellation and synchronous request timeout notice. Results retain their original range independently of active cache.
- Completed runs are listed offline. Opening validates every manifest artifact. Corruption, update failure, or an all-failed run preserves prior active identity and dates. An all-failed run is shown as update results without becoming active.
- Only successful items are selectable for use. Shows item status/reason/time, native-currency daily data, manifest, update log and relevant CSV exports. Revalidates active disk contents before display/export/use; corrupt evidence disables use while preserving identity/date.
- Callback hands exact generated import CSV bytes to S02 before sidebar radio instantiation, using adjusted_price/decimal, filename containing run_id, and supplier containing Yahoo chart/run_id/raw sha256. It resets old mapping/default/date settings, rotates uploader generation and clears stale token. Bundle remains uncommitted and unchanged. HKD=X explains HKD per USD and only exports daily data.

## TDD evidence

Initial RED command: `python -m pytest tests/test_downloads_view.py -q`

Result before implementation: **3 failed**, each `ModuleNotFoundError: No module named 'app.views.downloads'`. Expected because the specified page did not exist.

Additional RED command: `.venv/bin/python -m pytest tests/test_downloads_view.py -q`

After adding stale-default and failed-run acceptance assertions: **2 failed, 2 passed**. Assertions showed stale default_asset_id remained `stale`, and opening an all-failed run replaced dl_active. Implemented resets and a success-item guard afterward.

Final GREEN command: `.venv/bin/python -m pytest tests/test_downloads_view.py tests/test_data_center.py -q`

Result: **17 passed in 3.66s** (4 new view tests, 13 existing S02 regression tests).

Coverage includes zero automatic downloads, plan/cancel, parameter invalidation, explicit start, mixed status rows, update failure retention, verified offline opens/exports, corrupt open retention, precise CSV handoff bytes and supplier, stale upload state/token and defaults, bundle preservation, and FX import exclusion. Fixtures are generated exclusively with injected offline transport into temporary roots; real download caches are never changed.

## Investigation and self-review

An intermediate command used global `python`, whose Streamlit environment produced three existing S02 AppTest stale-widget KeyErrors after override/alias reruns. Read systematic-debugging instructions, inspected traceback and narrow diffs, then isolated interpreter difference: the repository `.venv/bin/python` passed all 17 targeted tests without changing existing tests or override behavior. Use the repository virtual environment for reproducible checks.

Self-review strengthened all-failed-run handling and old S02 defaults/date reset, and replaced initial copies of real caches in tests with deterministic offline generated fixtures. Supplier widget initialization now avoids simultaneously specifying a default and setting handoff state. No core files changed, no online calls, no full-suite run, no automatic commit or bundle save.

Files changed: `app/views/downloads.py`, `app/main.py`, `app/views/data_center.py`, `tests/test_downloads_view.py`, this report.

## Limits

Download execution is synchronous and cannot be interrupted using the page after start; the UI explicitly states this and the per-request timeout. AppTest simulates stale uploader session state; controller is validating a real mounted browser upload separately. Existing S02 global CSS predates this change and was not modified. No remaining implementation concern identified in this scope.
