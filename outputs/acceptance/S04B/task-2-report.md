# Task 2 — reference downloads UI

Status: DONE.

Implemented the sixth native Streamlit page 因子与官方汇率. Data import remains the default. The page validates explicit month-start plans, shows Chinese identity and unit metadata, request bounds, fixed page size, cancellation and source caveats. Only the explicit start action invokes the reference runner. Navigation, preparation, cancellation, cache opening and exports are offline.

Active cache and last attempt each carry root/run/manifest bindings. A new attempt does not activate a snapshot. Opening a record without successful items retains the prior usable cache. Every render verifies complete snapshot integrity, schema 2, current root, and exact bound manifest before exposing its exports. All-failed attempts retain manifest/raw audit exports; partial tables preserve missing values and appear only as diagnostic exports. Success CSV and source response exports use exact verified stored bytes. No DataBundle writes or import handoff were added.

## TDD and checks

RED (before creating the view or navigation entry):

`.venv/bin/python -m pytest tests/test_reference_downloads_view.py -q > outputs/acceptance/S04B/task-2-red.log 2>&1`

Outcome: 4 failed, as expected. Two failures identify missing `app.views.reference_downloads`; remaining failures identify the absent sixth sidebar option. Log retained at task-2-red.log.

Initial GREEN:

`.venv/bin/python -m pytest tests/test_reference_downloads_view.py -q > outputs/acceptance/S04B/task-2-green.log 2>&1`

Outcome: 4 passed in 1.15s. After adding broader offline behavioral checks, final GREEN and regression command:

`.venv/bin/python -m pytest tests/test_reference_downloads_view.py tests/test_downloads_view.py tests/test_data_center.py -q > outputs/acceptance/S04B/task-2-green.log 2>&1`

Outcome: 24 passed in 4.98s, exit 0. Final log retained at task-2-green.log. Six new AppTests cover no automatic download, prepare/cancel/change/navigation, invalid month-start dates, explicit one runner call, failed-run and failed-start retention, cache opening, mixed success/partial scope, NaN diagnostics, exact CSV/raw bytes, root changes, changed valid manifests, corrupt artifacts, schema 1 rejection and no import handoff. Fixtures invoke the real reference writer with offline ZIP/response payloads in temporary directories; no supplier calls.

## Files changed

- app/views/reference_downloads.py
- app/main.py
- tests/test_reference_downloads_view.py
- outputs/acceptance/S04B/task-2-red.log
- outputs/acceptance/S04B/task-2-green.log
- outputs/acceptance/S04B/task-2-report.md

## Self-review and concerns

Reviewed current-root binding, every export gate, partial diagnostics and same-run audit suppression, explicit-start semantics, page routing and supported reason labels, including Chinese TLS failure. Main changes only add the sixth route. No dependencies, core changes, original-page changes, Git actions or real-cache writes. The formal pre-existing real run remains untouched. HKMA online success is not claimed; UI supports transport/TLS unavailable results and discloses observation-month coverage limitations.

No known implementation concerns. The root controller owns any broader integration/full-suite verification.
