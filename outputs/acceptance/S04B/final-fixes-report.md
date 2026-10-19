# S04-B final fixes report

Status: DONE. No Git operations, network requests, core/UI changes or formal cache changes.

Implemented the Important auditor fix in `scripts/verify_reference_downloads.py`. The independent HKMA evidence reader validates a complete page before adding its observations: header, records shape, page size, canonical dates, finite positive values, requested interval and strictly increasing dates across pages. Failed/partial/cancelled items can retain a rejected final response; the auditor stops reading observations at that response and verifies every exported diagnostic value against earlier valid pages. A purported success fails closed on invalid raw evidence. Expected decoding/data exceptions are bounded; artifact reads and snapshot integrity checks remain in place and are not bypassed. No production parser is called. Touched auditor traversal was expanded for readability; no core validation refactor was attempted.

## TDD evidence

RED command (before implementation):

`.venv/bin/python -m pytest tests/test_reference_verification.py -q > outputs/acceptance/S04B/final-fixes-red.log 2>&1`

Observed: **15 failed, 1 passed in 0.47s**. The new real-run regressions failed on rejected JSON/structure/value/date responses (including cancellation after response) and altered diagnostic data. The existing missing-month regression passed. Expected failures included JSONDecodeError / UnicodeDecodeError / AttributeError and acceptance of malformed evidence after status tampering. Full output: `final-fixes-red.log`.

GREEN command (after implementation):

`.venv/bin/python -m pytest tests/test_reference_verification.py tests/test_reference_updates.py -q > outputs/acceptance/S04B/final-fixes-green.log 2>&1`

Observed: **60 passed in 0.64s**, pristine output. Full output: `final-fixes-green.log`.

Tests cover a full valid first page (page_size=1) followed by malformed HTTP 200 JSON, non-JSON, invalid UTF-8, malformed records structure, rejected header, invalid numeric value or invalid date. Each uses the actual snapshot publisher, retains one diagnostic row and two raw responses, preserves parse_error or cancelled status/reason, returns all-sources false and table_checked true. Every variant also changes the manifest to claim success and proves rejection. A separate test changes an exported diagnostic value and updates its integrity metadata to prove semantic comparison still fails. Existing monthly coverage and downloader tests remain passing.

## Files changed

- `scripts/verify_reference_downloads.py`
- `tests/test_reference_verification.py`
- This report and `final-fixes-red.log`, `final-fixes-green.log`

## Self-review and concerns

Reviewed complete-page validation, fail-closed success behavior, exception scope, independent-parser requirement, and retained artifact integrity. Rejected pages contribute no observations, including partially valid rejected pages; every table row must match valid prior observations. Raw files still pass the loader's full hash/size/path checks before traversal. No broad reader framework or unrelated refactor was introduced. No blocking concerns. Full suite and final independent review remain controller responsibilities as requested. The formal snapshot is untouched; there was no second live attempt.

## Controller review amendment: integrity gate scope

The controller found that the second artifact read was inside the bounded parse exception handler. Its ValueError could therefore be mistaken for malformed source data if disk integrity changed after the initial snapshot load. Moved `read_artifact` outside the parser try block so all artifact verification failures propagate. Only `_hkma_observations(body, ...)` remains inside the bounded data-error handler.

Added an injected `read_artifact` ValueError regression on the second raw page of a real failed diagnostic snapshot, without changing any raw cache bytes. It proves the auditor propagates a late integrity failure instead of claiming verified integrity.

RED command:

`.venv/bin/python -m pytest tests/test_reference_verification.py tests/test_reference_updates.py -q > outputs/acceptance/S04B/final-fixes-integrity-red.log 2>&1`

Observed **1 failed, 60 passed in 0.63s**: the new regression failed with DID NOT RAISE ValueError, demonstrating the swallowed integrity failure.

GREEN command after moving the read:

`.venv/bin/python -m pytest tests/test_reference_verification.py tests/test_reference_updates.py -q > outputs/acceptance/S04B/final-fixes-integrity-green.log 2>&1`

Observed **61 passed in 0.61s**, pristine output. Self-review confirmed that verified-byte reads now sit outside the data parsing exception handler; integrity exceptions cannot be treated as rejected source pages. No other behavior or files changed beyond the scoped auditor/test/report/log amendments. No remaining concerns.
