# Task 2 — daily HKD three-step page

Status: DONE. No Git repository; no commit created. Scoped diff: `task-2.diff` against the baseline directory recorded in `backup.txt`.

Implemented native Streamlit page 「日线港币查验」 alongside all seven existing pages. Price selection, target months and adjusted-price confirmation precede explicit FX source selection (SYNTH samples, HKMA official cache, Yahoo unofficial cache, or CSV/XLSX + sheet). HKD hides USD requirements and uses the core fixed-1 behavior. Default confirmations are false; age is integer 0–7. Explicit compute calls the supplied core; no financial formula is duplicated in the page.

Independent sample module uses C1 month validation and actual exchange sessions; prices start at 100 then grow 10% per month, FX endpoints start 7.8 then add 0.1. Missing last price session, missing final FX month, stale quote and duplicate latest date have diagnostic examples. Labels and the input-combination caption distinguish SYNTH, actual cache and imported source; mixed synthetic/actual inputs are explicitly demonstrations.

All source modes, cases, symbol, months, confirmations, age, resolved roots, cache manifests, upload bytes/name/sheet and provider choice enter the invalidation token. Both selected raw caches are verified on every render; changed parameters retract old result and result exports. Corrupt evidence clears state, reports Chinese errors and disables compute. Upload uses existing `read_file`, retaining raw bytes, physical row and sheet provenance. The two-row sample template is an input download, distinct from result exports.

Results include Chinese reasons, target/preview counts, local/FX/cross/HKD percentage comparison, actual price/FX endpoint dates and ages. Six raw tables plus metadata have CSV/JSON downloads. Current-vintage valuation, asynchronous observations, age hypothesis, missing historical eligibility and no save/handoff limitations are visible. Existing CSS and dependencies are untouched.

## TDD evidence

RED command: `.venv/bin/python -m pytest tests/test_daily_hkd_view.py -q`.
Exact full output: `task-2-red.log`.
Relevant output: `8 failed in 1.66s`; page tests failed because 「日线港币查验」 was absent from sidebar options; sample/helper test failed because new module was absent. Tests were written and executed before production implementation.

Initial focused run after implementation: `task-2-focused.log` contained `1 failed, 7 passed, 2 warnings in 1.95s`. The remaining failure exposed binary float representation in the promised exact 7.9 sample value. Synthetic values now round to 10 decimal places without affecting conversion formulas.

Additional real cache lifecycle regression RED: `task-2-cache-switch-red.log`, command `.venv/bin/python -m pytest tests/test_daily_hkd_view.py tests/test_daily_monthly_view.py tests/test_smoke.py -q`; `1 failed, 33 passed, 2 warnings in 11.09s`. Switching from empty HKMA to available Yahoo retained a selectbox None and disabled compute. Fixed by clearing invalid cached run selection before rendering its native selector.

Final GREEN command: `.venv/bin/python -m pytest tests/test_daily_hkd_view.py tests/test_daily_monthly_view.py tests/test_smoke.py -q`.
Exact output: `task-2-green.log`.
Result: `34 passed, 2 warnings in 11.38s`.

The 12 new test cases cover default empty result/result exports, hand-calculated 11.410256% conversion, both confirmations, HKD bypass, each bad FX example, missing final price, changed age/month/confirmation/resolved roots/manifests, empty caches, real HKMA/Yahoo cache conversion and corrupt raw-evidence retraction, price cache immutability, DataBundle immutability, no Yahoo network request, sample provenance, CSV physical rows, XLSX sheet provenance, and upload bytes/name/sheet/error lifecycle. Native upload transport is substituted because AppTest does not support setting uploaded files; the page lifecycle and existing CSV/XLSX parser run for real.

## Changed files

- `app/views/daily_hkd.py` (new)
- `src/portfolio/data/daily_hkd_samples.py` (new)
- `tests/test_daily_hkd_view.py` (new)
- `app/main.py` (only page option and branch appended)

## Self-review and concerns

Reviewed scope, input-token coverage, per-render cache checks, source provenance and C1 blocked propagation. No core interface mismatch. Result downloads consistently use `dh_download_*`; input template uses `dh_template`. Cache discovery conservatively rejects malformed manifests while listing candidate runs, so a corrupt unselected snapshot can require repair before the source is usable; this is safe but restrictive.

The two warnings come from installed `exchange_calendars` XHKG calendar NumPy timedelta deprecation, also used by C1; no dependency change or suppression was introduced. Browser screenshots and native download acceptance are handled by the controller. C3 historical availability and S05 candidate/portfolio work remain outside this delivery.
