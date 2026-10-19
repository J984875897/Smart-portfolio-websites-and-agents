# S02 core review fixes

DONE: Four Important findings addressed. Owned importer.py and tests/test_importer.py, tests/test_quality.py only; contracts.py/quality.py needed no edits. No Git, dependency, UI, network or downstream-stage work.

Root causes inspected against review, existing implementation/API and approved S02 design: listing conflicts checked sequentially rather than whole asset groups; truthiness discarded zero; pandas skipped physical blank lines before synthesized row numbering; duplicate status overwrote review and bypassed metadata acceptance.

TDD commands (every RED redirected/appended to outputs/acceptance/S02/review_red_checks.txt; corresponding GREEN to review_green_checks.txt):

1. `.venv/bin/python -m pytest tests/test_importer.py -k listing_disagreement -q`: RED exit1 four expected assertion failures [valid,blocked] vs [blocked,blocked]; minimal group listing check; GREEN exit0 4 passed,15 deselected. Parameterized currency, exchange, share class and ticker, both input orders; commits contain no assets.
2. `.venv/bin/python -m pytest tests/test_quality.py -k dataframe_zero -q`: RED exit1 zero blocked instead of valid; explicit missing-scalar normalization; GREEN exit0 1 passed,6 deselected. DataFrame nullable numeric zero/missing/two and CSV equivalent, .0 retained.
3. `.venv/bin/python -m pytest tests/test_importer.py -k physical_start -q`: RED exit1 [2,3,4] vs [2,4,6]; csv.reader physical record start-line attr; GREEN exit0 1 passed,19 deselected. Includes blank line, multiline quoted name, malformed value issue, accepted observation and all provenance traces.
4. `.venv/bin/python -m pytest tests/test_quality.py -k 'duplicate_extreme or duplicate_monthly' -q`: RED exit1 2 expected failures, pending duplicate created asset and monthly duplicate bypassed review; independent is_duplicate plus review promotion; GREEN exit0 2 passed,7 deselected. Fresh repeated70% rows produce no assets/aliases/history/observations until ACK, then one .7 observation. Existing identical70% classification correction preserves equity/history without ACK, applies one bond history entry with ACK without new observation. Monthly repeated collision rows both pending until ACK, then only one new observation.
5. `.venv/bin/python -m pytest tests/test_importer.py tests/test_quality.py -q`: exit0 **29 passed in 0.59s**, retaining all21 previous checks. Full suite intentionally not repeated per controller.

API delta: ImportPreview.rows boolean is_duplicate independent of status. Valid duplicates retain duplicate status compatibility; review duplicates stay review. Commit gates acceptance before metadata, then uses boolean to prevent observation insertion. No persistence schema change. CSV read_file attrs source_rows is physical start-line sequence, used by preview. Explicit rectangular CSV validation now raises ValueError for wrong-width rows. Direct DataFrames use sequential indices unless carrying parser source_rows attrs. Existing precondition applies: preserve read_file frame record order and attrs; preview/commit use same existing bundle, callers do not mutate preview/config between phases.

No known unresolved review findings. Reviewer should independently re-review fixes before UI. Logs contain actual pytest output for all RED/GREEN commands.

## Second narrow review pass

Read latest review including Important5 duplicate headers and Important6 incomplete listing matching. Added regressions before each fix.

6. `.venv/bin/python -m pytest tests/test_importer.py -k duplicate_column_names -q`: RED exit1 3 failures (CSV,XLSX,DataFrame did not raise); explicit unique-header/columns invariant before conversion; GREEN exit0 **3 passed,20 deselected in0.58s**. XLSX original header read before pandas mangles labels. ValueError message: Duplicate column names: headers must be unique before mapping.
7. `.venv/bin/python -m pytest tests/test_importer.py -k distinct_stable_ids -q`: RED exit1 1 assertion failure second missing-ticker stable ID blocked; exact-listing/alias lookup now requires exchange,ticker,currency and commit omits incomplete aliases; GREEN exit0 **1 passed,23 deselected in0.26s**. Two explicit stable IDs succeed in same file and sequential bundles; each canonical refiling remains duplicate/idempotent, assets/observations remain2, provenance remains correct, aliases stay empty; no stableID+no ticker still blocked. No fuzzy matching introduced.
8. `.venv/bin/python -m pytest tests/test_importer.py tests/test_quality.py -q`: exit0 **33 passed in0.61s**, including previous listing-conflict regressions for complete nonempty listings. Actual output appended to existing review RED/GREEN logs. No fullsuite repetition/UI/dependency/Git work.

API clarification: complete automatic listing identity requires exchange,ticker,currency; optional blank share_class remains allowed. Explicit stable ID is sufficient with no ticker if other quality fields valid. Incomplete configured aliases are not consulted. Headers must be unique across CSV,XLSX,direct DataFrame; ambiguity raises actionable ValueError for UI display. No new public fields beyond previously reported is_duplicate/source_rows.
