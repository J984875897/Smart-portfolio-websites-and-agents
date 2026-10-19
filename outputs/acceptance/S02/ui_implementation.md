# S02 UI implementation report

DONE. Implemented only owned app files, .streamlit/config.toml and tests/test_data_center.py, plus acceptance test logs. No Git, dependency, core, S03 or S04 changes. Installed portfolio.data public API used without src path hacks; app/main.py places project root on path only for app.views imports.

## Interface

Chinese local research data desk, approved white/light-blue-gray/navy/lake-blue colors, local PingFang/system font and monospace codes. Native Streamlit controls and tabular content. Visible S02, original currencies and SYNTH labels. Actual numbered sequence: file/raw → explicit mapping/defaults → quality → saved bundle. No finance calculation, optimization, eligibility count or network call.

CSV/XLSX uploader, actual workbook sheet selection, synthetic ten/repeated/dirty buttons using identical read_file/preview_import/commit_import route. Actual fixtures live under tests/fixtures/imports; brief's fixtures/imports path did not exist. CSV/XLSX templates and all three sample CSV downloads provided. Raw preview display clears attrs only on a copy to avoid serializing raw bytes; original parser frame retains source physical-line trace and sheet attrs.

All canonical fields explicitly selectable, exact-name suggested defaults only, no hidden mapping or class-name inference. Single-product stable-ID/ticker/name/exchange/share defaults and explicit tool/economic/currency/frequency defaults. Price vs adjusted price vs total/price return, decimal/percent, declared date format and source supplier. Blank default type/class retained until selected. Core enum codes displayed with Chinese descriptions.

Full quality rows and full issues shown and downloadable with source filename/sheet/row; display includes Chinese status and issue explanations while original codes and core English detail remain. Review acknowledgement starts unchecked; blocked rows remain blocked; save button expressly says only accepted rows are saved. All-blocked/no-ack review-only imports disable save. Legitimate 70% dirty return requires acknowledgement and stays .7. Repeated observations use core is_duplicate behavior.

Classification editor selects asset ID and has preserve-current blank choices: only explicitly selected fields enter core classification_overrides, preserving untouched tool/economic fields. Rechecking mandatory. Manual alias editor uses explicit source ticker/exchange/currency/share class and existing target asset ID; no technical JSON input. Aliases route through config alias_mappings, not raw mutation. Classification original/new/source/time audit comes from core.

Fingerprint covers raw bytes, filename, selected sheet, all mapping/defaults/supplier/units/date settings, classifications, aliases and current saved bundle version. Changed config invalidates preview, removes commit and clears acknowledgement. New sample/file bytes clear overrides/aliases/ack; explicit classification/alias updates invalidate and rerun. Preview and commit receive the same current bundle.

Save builds independent candidate and changes session bundle only after candidate.save succeeds. Version folder uses UTC timestamp plus random suffix under fixed data/processed/imports; PORTFOLIO_IMPORTS_ROOT is a trusted test environment override, not a user filesystem control. Failed save preserves prior bundle and current preview, with Chinese actionable error. Prior versions selectable after restart; load validates core hashes before replacing bundle. Failed/corrupt load preserves current state. Empty supplier gets scoped Chinese error and invalidates preview/ack. Malformed XLSX ZIP/XML exceptions get scoped Chinese errors.

## Verification

Command `.venv/bin/python -m pytest tests/test_data_center.py -q`: **12 passed in 3.42s**, exit 0, no pytest warnings. Final fresh output outputs/acceptance/S02/ui_green_checks.txt. RED outputs outputs/acceptance/S02/ui_red_checks.txt contain initial missing UI assertions, missing manual-alias controls/all-blocked save enabled, and reproduced empty-supplier exception/default classification overwrite/malformed XLSX traceback before corrections. Later expanded cases exercise existing safeguards; do not claim each expansion introduced a previously absent behavior.

Tests interact with real AppTest widgets and real portfolio core/disk:
1. empty state, preview does not commit, ten then repeated-two remains ten products/observations;
2. supplier config invalidates preview and removes commit;
3. dirty blocked rows, unchecked acknowledgement, accepted .7 return, audited classification;
4. fresh independent AppTest opens disk version;
5. missing value mapping blocks every row and disables save;
6. actual alias resolution for alternate ticker ALT maps to p0, recheck required and persisted alias does not inflate product count;
7. simulated PermissionError during save preserves prior bundle and preview;
8. unit/mapping/file switch clears preview and previous review acknowledgement;
9. corrupt persisted observations rejected without replacing current bundle;
10. empty supplier scoped error;
11. economic-only override sends only economic field, preserves tool type;
12. malformed workbook parser error scoped without AppTest exception.

## Limits and handoff

No browser tools are available. AppTest does not exercise actual browser file-uploader selection or download delivery; sample controls use the same parser pipeline, and malformed XLSX/alternate ticker tests inject local source bytes into session state explicitly. No screenshots or visual-browser claims. Real XLSX parsing/core parity covered by controller/core tests, not new UI upload automation. Controller must run actual Streamlit HTTP startup/health and full suite/review. Launch `.venv/bin/streamlit run app/main.py` from workspace root; config binds localhost.

No arbitrary directory picker, no remote assets/fonts/network, no S03/S04 placeholders in UI. Stored empty fx/factors remain core contract fields and are not shown as completed features.

## Important 7 followup

Identical upload reselection after sample fixed by resetting upload_token when the uploader returns None. Mounted unchanged uploads retain token so samples remain active on reruns. Exact mocked-uploader AppTest regression observed RED (user.csv remained SYNTH_dirty_data.csv), then GREEN: 13 UI tests passed in 3.84s; all prior 12 retained. See /private/tmp/cityu-s02-ui-fix-report.md and outputs/acceptance/S02/ui_review_red_checks.txt / ui_review_green_checks.txt. Browser upload automation remains unverified.
