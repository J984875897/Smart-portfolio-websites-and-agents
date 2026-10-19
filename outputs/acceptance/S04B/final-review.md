# S04-B final whole-change review

**Mode:** PR Review (requesting-code-review template; Brooks review risk calibration).
**Scope:** Final S04-B code diff against `/private/tmp/portfolio-s04b-before`, its 11 changed/new code and test files, approved design and implementation plan, task reports/reviews, acceptance evidence, root README and workflow scope statements. No Git repository. Highest-risk inspection covered request initiation, parser identity/units, pagination and failure transitions, schema compatibility/integrity, UI bindings and the independent acceptance auditor.
**Health Score:** 94/100 (one Important, one Minor; balanced calibration). This score concerns the reviewed change, not the whole application.

## Strengths

- `src/portfolio/data/reference_updates.py:26`, `src/portfolio/data/reference_updates.py:82`: Invalid plans are rejected before I/O, every returned response is saved before status/parsing decisions, and immutable run publication preserves earlier versions. Transport errors use fixed classifications without persisting exception messages.
- `src/portfolio/data/providers/french.py:10`, `src/portfolio/data/reference_updates.py:100`: French monthly parsing preserves sentinel missing values and converts percentages once; exact archive identity and model columns prevent cross-model/region substitution. The full raw CSV remains separate from the requested-month table. S01 imports retain their parser compatibility.
- `src/portfolio/data/reference_updates.py:91`: HKMA offsets advance by actual returned rows, ordering/range checks reject overlapping or invalid pages, and a full page at the cap remains partial. Success requires requested-month observations and page exhaustion. No daily-calendar or historical-availability certification is implied.
- `src/portfolio/data/snapshots.py:95`: Schema 2 checks identity, evidence references, hashes/sizes, timestamps, paths and unexpected files while retaining Yahoo schema 1 behavior. The future writer identifies `reference-v2`; the loader accepts the original `reference-v1` snapshot. The previous TLS and UTC review findings are resolved.
- `app/views/reference_downloads.py:88`, `app/views/reference_downloads.py:149`: Only the explicit start action calls the runner. Plan invalidation and bound root/run/manifest verification prevent stale parameters or changed caches from becoming silently usable. Failed attempts retain the opened successful cache; successful CSV and raw exports use stored verified bytes, and partial exports remain diagnostic.
- `tests/test_reference_updates.py:26`, `tests/test_reference_downloads_view.py:46`: Offline tests exercise real parsers, archives and snapshot files through transport seams, including cancellation, partial coverage, integrity failure, failed-run retention and exact export bytes. The recorded full suite is **311 passed in 23.98s**. The browser evidence records 1440/720 widths, no visible exceptions, no new runs during preview/cancel/cache opening, and byte-exact native CSV export.
- Acceptance documentation accurately distinguishes the four successful French downloads (12 months each, 240 independently checked numeric cells) from HKMA's unavailable live connection. The original manifest keeps `transport_error`; the later TLS classification fix does not rewrite historical evidence. No S05, formal candidate eligibility, daily calendar completeness or historical publication-time claims were introduced.

## Issues

### Critical (Must Fix)

None found.

### Important (Should Fix)

1. **Replay auditor crashes on a deliberately retained rejected HKMA page.**

   **File:** `scripts/verify_reference_downloads.py:75` (and the page traversal starting at line 72).

   **Symptom:** The auditor parses every HTTP-200 response as valid JSON whenever a diagnostic table exists. The downloader deliberately retains malformed HTTP-200 bodies after valid earlier pages and marks that item `unavailable / parse_error`. A focused in-memory probe supplied one valid first page and `b'{'` as the second response: the core retained one diagnostic row and two raw pages, but `verify()` raised `JSONDecodeError` instead of returning the incomplete-source report. Malformed structures in rejected pages can similarly fail the traversal.

   **Source:** *Code Complete* — defensive programming and error-handling discipline; the evidence reader assumes every saved successful HTTP response is a parsed data page even though the writer's contract distinguishes those states.

   **Consequence:** The documented `--replay RUN_ID` command cannot audit a supported failure snapshot and exits with an uncaught traceback before writing its report. This breaks the offline diagnosis path precisely when retained raw evidence is needed. The already recorded formal French-success/HKMA-no-response snapshot is unaffected.

   **Remedy:** Independently distinguish valid observation pages from rejected malformed evidence while comparing the retained table to accepted raw observations. Preserve the failed item status/reason and raw evidence, and fail closed for malformed evidence in a purported successful item. Add a focused offline regression with a valid first page followed by malformed JSON/structure, confirming the replay report preserves the failure and still verifies the valid diagnostic rows. Do not rewrite the original live snapshot or use a new live request for this fix.

### Minor (Nice to Have)

1. **Dense validation and transition expressions make later policy changes harder to inspect.**

   **Files:** `src/portfolio/data/reference_updates.py:95`, `src/portfolio/data/reference_updates.py:117`, `src/portfolio/data/snapshots.py:110`, `src/portfolio/data/snapshots.py:130`.

   **Symptom:** Several correctness-critical branches combine multiple unrelated predicates or nested conditional expressions on a single line. This is visible in page interval checks, table accumulation, coverage status selection and manifest/page validation.

   **Source:** *Code Complete* — readability and defensive programming; *A Philosophy of Software Design* — cognitive load.

   **Consequence:** A reviewer must mentally split long expressions to verify which failure state or invariant each condition controls. Future pagination/schema changes are more likely to miss a branch. No current incorrect result was established from these expressions.

   **Remedy:** When next touching these blocks, expand the guards and give coverage/validity predicates descriptive names. Preserve behavior and the existing boundary tests; no broad refactor is required for acceptance. This independently confirms the earlier core review's nonblocking concern.

## Recommendations

Fix the auditor failure path in one focused change and re-review that diff with its regression evidence. Avoid unrelated production refactoring. Keep the existing live snapshot and source limitations unchanged, and only finalize the pending workflow/plan status after the fix passes review.

## Assessment

**Spec readiness:** Core downloader and UI comply with the approved S04-B contracts. Final delivery needs the auditor's supported failed-page replay path fixed.

**Ready to accept? With fixes.** The main feature is well bounded and backed by meaningful offline and recorded live evidence. One concrete Important defect remains in the new acceptance/replay script; the formatting concern is nonblocking.

**Review verification:** Read-only static inspection and review of the supplied reports/logs. No reported passing suite or live request was rerun. One focused probe ran with `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src .venv/bin/python`; it exercised `_download` with injected responses and in-memory artifact storage, then the actual auditor with in-memory read seams. Output: `core_status=unavailable`, `core_reason=parse_error`, `diagnostic_rows=1`, `raw_pages=2`, `auditor_error=JSONDecodeError`. No real cache, original manifest, application source, or test file was modified; only this requested report was written. Browser and full-suite results remain controller-recorded evidence, not independent reruns.

## Reassessment after the final auditor fix wave

**Important finding: Resolved.** `scripts/verify_reference_downloads.py:21` independently validates a complete HKMA page before any observations enter the comparison map. `scripts/verify_reference_downloads.py:99` stops at a rejected response for failed/cancelled diagnostic runs, preserves the item's failure status and reason, and rejects the same evidence when success is claimed. Diagnostic table rows must still match valid prior raw observations (`scripts/verify_reference_downloads.py:111`). This fixes the demonstrated malformed-page replay failure without using the production parser or changing stored source evidence.

**Integrity handling: Approved.** The verified artifact read at `scripts/verify_reference_downloads.py:103` occurs outside the bounded source-parsing exception handler. Hash/path/file failures therefore propagate and cannot be reported as merely rejected supplier data. Only decoding and data validation errors from the independent page parser enter that handler.

**Regression evidence:** `tests/test_reference_verification.py:41` covers malformed JSON, text, UTF-8, records, rejected headers, invalid numbers and invalid dates, both after normal receipt and after cancellation. It checks retained diagnostic comparisons, unchanged failure classifications, incomplete-source reporting and rejection of a tampered success claim. `tests/test_reference_verification.py:76` independently tests a changed diagnostic value with updated integrity metadata; `tests/test_reference_verification.py:96` tests a late artifact-integrity failure. Reviewed reported RED **15 failed / 1 passed**, GREEN **60 passed**, integrity amendment RED **1 failed / 60 passed**, and final focused GREEN **61 passed in 0.61s**. No tests were rerun by this reviewer.

**Remaining findings:** Critical: none. Important: none. Minor: the previously recorded dense core validation expressions remain nonblocking. No unrelated refactor is required.

**Updated health score:** 99/100 for this reviewed change (one nonblocking Minor).

**Spec and code-quality readiness: Approved. Ready to accept: Yes, once the controller's already-running final full-suite verification and pending status updates finish.** The auditor now handles the supported failed-page evidence path while retaining integrity and semantic checks. At this re-review, the final full-suite log was still in progress; no final count is asserted here. The earlier source limitations remain unchanged: four French sources have recorded live evidence, HKMA remains unavailable online, and this step provides no daily-calendar, historical-availability or candidate-eligibility certification.

**Re-review scope:** Only the auditor/test fix wave, its report and focused log evidence were inspected. No live requests, real-cache mutations, original-manifest edits, or broad test reruns occurred. Only this report was appended.
