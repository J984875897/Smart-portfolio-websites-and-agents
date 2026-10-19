# Final S02 integration review

Decision: **changes required** for one Important UI source-selection finding. Prior S02 core spec/quality approval remains valid, with all six historical findings resolved; see `/private/tmp/cityu-s02-review-report.md`. No Critical finding.

Reviewed binding S02 brief, complete core/UI/test/script/package diff, current UI and AppTest assertions, UI implementation report, verification script and generated import summary. Did not rerun covered suites. Ran one small AppTest reproduction with a mocked uploader response, without saving files or altering implementation. No network/install/Git operation.

## Important 7 — Re-uploading the same real file after a sample silently retains the sample

Location: `app/views/data_center.py:97-107`.

Trigger: upload `user.csv`; load a SYNTH example; remove the file from the uploader; upload the identical `user.csv` again. `upload_token` remains the previous `(name, SHA)` when the uploader is cleared or a sample is chosen. The subsequent upload therefore fails the token-change check and does not call set_source.

Reproduced using real AppTest execution with streamlit.file_uploader mocked only to return a BytesIO file named user.csv, then None, then the same file. Outputs were `initial user.csv`, `sample SYNTH_ten_products.csv`, `reupload same file SYNTH_ten_products.csv`, zero AppTest exceptions. No commit was performed. This is a state-transition test, not a claim of browser uploader automation.

Consequences: a normal reselection cannot restore the user's file; the uploader shows the real filename while the active source remains synthetic. Users must rename/change the file or restart to proceed. Preview invalidation is never triggered for the intended new source, because the new selection was ignored.

Remedy: reset the dedup upload token when the uploader is cleared, or model explicit active-source selection/file selection events. Ensure switching to a sample does not immediately auto-switch back on the next widget rerun merely because the old upload remains mounted. Add the exact upload → sample → remove → same upload regression, asserting source/preview/ack/type-unit state transitions.

## Spec and quality assessment otherwise

- Core distinctions, stable identity, exact aliases, documented classification audit, source trace and review-before-commit remain as previously approved.
- Config fingerprint includes file, sheet, mapping, defaults, provider label, unit/convention, corrections, aliases and bundle version; ordinary config changes invalidate preview and acknowledgement.
- Commit constructs a separate candidate and updates session state only after successful local persistence. Load failures preserve the current bundle. Existing tests cover save PermissionError and corrupt table hashes.
- Classification selections only send explicitly changed fields; manual aliases use the core mapping API. Classification/alias application requires another quality check.
- CSV/XLSX mapping and templates are available, source diagnostics remain visible, and blocked/review-only rows cannot be saved without eligible rows/acknowledgement.
- Local output paths are fixed under project data/processed/imports unless a trusted test environment override is set. Acceptance script output is explicitly configurable and version bundles are unique. No user-controlled arbitrary UI path is exposed.
- Offline acceptance script verifies frozen S01 source hashes, retains original adjusted-price currencies and blocks the identified missing price. Its observed summary records 10 synthetic assets after repeat, .02 conversion, 3 real imported products/8305 observations, and explicitly false candidate_eligibility_checked/hkd_returns_computed. It does not present product imports as formal universe eligibility or compute fake HKD returns.
- No downstream S03/S04/S05 implementation expansion observed.

## Nonblocking note and evidence limits

The earlier Minor readability concern about dense core statements remains future maintenance work, not a gate blocker. UI source transitions merit explicit state handling, as illustrated by the new finding. Full native browser file selection/download delivery and visual screenshots were not verified; AppTest and supplied HTTP/health evidence do not establish those browser behaviors. Existing regression evidence is useful but did not cover uploader removal/reselection.

Overall S02 spec/quality approval is withheld only pending Important 7's fix and narrow re-review. The prior six findings need not be reopened or rerun.

Final supplied evidence inspected: `outputs/acceptance/S02/test_checks.txt` ends `90 passed in 14.17s`; `server_checks.json` records localhost8501 homepage200 and health200/ok. These successes do not cover or resolve Important7.

# Final narrow re-review: Important 7 resolved

**S02 spec compliance: approved. S02 code quality: approved. No unresolved Critical or Important review findings remain.** All six core findings and the final UI source-selection finding are resolved; previous review history above is preserved.

Reviewed the minimal uploader token change, new AppTest regression and fix report, and actual `ui_review_green_checks.txt` ending `13 passed in 3.84s`. Did not rerun the suite.

The None-uploader branch removes the remembered upload token, allowing deliberate reselection of identical name/bytes to call set_source. It does not disturb the current source merely because an upload is removed. Choosing a sample while an unchanged file remains mounted preserves the token, preventing the old upload from unexpectedly replacing the sample on later reruns. The added test covers the exact original reproduction, ordinary rerun preservation, restored visible source filename, cleared preview/acknowledgement and real-file price/decimal settings.

Existing source captions identify the active file, including the SYNTH prefix when a sample is intentionally active. Actual native browser uploader/download delivery remains outside the verified scope; the new test accurately describes its mocked uploader boundary. Prior nonblocking readability note remains future maintenance, not an acceptance blocker. Controller's final full-suite/docs/HTTP verification can proceed independently of this completed review gate.
