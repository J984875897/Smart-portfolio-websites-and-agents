# Task 3 implementation report

Status: DONE. No Git commit: this workspace has no Git repository.

Implemented `scripts/verify_daily_hkd.py` and `tests/test_daily_hkd_verification.py` only; no src/app changes. Public `verify_legacy_hkd(manifest_path)` returns `(report, tables)`. CLI accepts required `--s01-manifest` and `--output`.

The auditor verifies all legacy manifest files, consumes the independent C1 audited raw price endpoints, reads FX original JSON directly, reconstructs London observation dates with ZoneInfo, independently selects same-month latest observations and checks duplicate/bad/missing/stale endpoints, then compares production endpoint labels/values/age/status/reasons, actual price dates, local/FX/cross/HKD values and historical eligibility. A deliberately changed production HKD return raises a mismatch. Missing latest-month FX and invalid latest quote remain matching blocked diagnostics; HKD native results remain valid.

Exports per-symbol reconciliation/metadata, full FX observations (including original missing quotes and their diagnostics), production FX endpoints, independent raw endpoint reference CSV and independent_verification.json. Metadata explicitly records legacy_offline_replay, current_vintage, new_download=false, historical_eligible=false, source manifest SHA256, raw SHA256, source_global_status and endpoint scope. Actual S01 FX remains globally partial; no source_status=success is inserted. This explicit imported raw-file endpoint diagnostic preview is distinct from loading the globally partial schema1 cache, which remains blocked by the production cache connector.

## TDD evidence

RED: `.venv/bin/python -m pytest -q tests/test_daily_hkd_verification.py` before implementation: five failures because `scripts.verify_daily_hkd` did not exist. Full output: task-3-red.txt.

GREEN (rerun after final date comparison): same command: 5 passed, 2 existing exchange_calendars NumPy timedelta deprecation warnings in 0.74 seconds (exact timing in task-3-green.txt). Covers hand arithmetic, invalid latest row without fallback, missing month diagnostic, changed raw rejection, changed production HKD detection.

## Real legacy replay

`.venv/bin/python scripts/verify_daily_hkd.py --s01-manifest outputs/acceptance/S01/snapshots/20261012T143920Z-6f4d426f/snapshot_manifest.json --output outputs/acceptance/S04C2/legacy_replay` completed with exit 0, rerun after final changes. Both comparisons agree and previews valid. SPY Jan2025 independently calculated local return 0.026856237777849623, FX return 0.0036323400428959207, HKD return 0.030586128808627544. HKD-native 2800.HK independently calculated HKD return 0.010869455644421322. Full stdout: task-3-replay.txt; reviewable artifacts: legacy_replay/.

## Self-review and limitations

Verified explicit global partial semantics and retained all raw FX observations. No network requests, installations or dependencies changed. No Gitbackup.txt created. Existing C1 verifier supplies independently audited price references; this script does not duplicate C1 calendar logic. Full suite, documentation, package reinstall, browser and final external review are controller responsibilities. Existing third-party deprecation warnings remain. No unresolved implementation concerns.
