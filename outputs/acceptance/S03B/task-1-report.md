# S03-B Task 1 evidence

Implemented only the alignment core, synthetic inputs, core tests, and offline acceptance script. No UI changes and no Git initialization.

## Interface

`align_monthly(reconciliation, timing, *, asset_ids, end_month, decision_at, months=60) -> AlignmentResult`

Inputs are DataFrames plus requested asset IDs, strict YYYY-MM end month, aware ISO datetime decision, and positive integer month count (booleans rejected). Requested end month may not exceed the decision month in Hong Kong. Return fields are `report`, `coverage`, `matrix`, `window_start`, `window_end`, `decision_at`. Window boundaries are ISO month-end date strings; decision is canonical UTC ISO. Matrix date index uses ISO date strings with index name `date`, sorted asset columns, decimal HKD floats, and exactly the requested number of rows even with no eligible assets.

Report columns: asset_id, status (eligible/excluded), valid_months, missing_months, reason. Missing count means blocked/missing required periods, rather than only absent input records. Coverage has one row per requested asset × fixed month: asset_id, date, status (valid/blocked), reason, hkd_return; complete raw row lists in reconciliation_evidence and timing_evidence; single rows flattened with reconciliation_ and timing_ prefixes. Duplicate and failed evidence remains inspectable rather than choosing an arbitrary row. `TIMING_FIELDS` exports the nine declared upload fields from the spec. File-backed timing source_file/source_sheet/source_row/source_hash are forcibly obtained from read_file attrs and raw SHA-256, overriding forged upload columns. Non-file DataFrames retain explicit provenance or receive deterministic generated provenance.

`sample_alignment_inputs()` returns `(reconciliation, timing, asset_ids)`. It builds a synthetic DataBundle with monthly total returns and FX inputs and calls real `reconcile_hkd`. It includes one older month to demonstrate that old history cannot replace missing window months. MISSING_END_FX uses EUR so its withheld final quote does not inadvertently block complete USD. All scenarios are artificial and isolated from imported bundles.

## Rules and reason codes

Each requested period needs exactly one S03-A row, valid status, finite HKD return >= -1, adjacent month-end start/end/date labels, and valid currency. Each needs exactly one timing row with strict month-end period date, supported market timezone, nonblank source_name, aware ISO price endpoints, foreign FX endpoints, and aware available_at. Price observations are converted to declared market timezone; FX endpoints use UTC calendar. Endpoint months must match the start/end labels; local date must be at most 7 calendar days before month-end. Availability must be >= every required observation and <= decision, with equality allowed. Source_name is a declaration of final monthly valuation semantics, not independent verification of a vendor or market calendar.

Codes: missing_return, ambiguous_return, invalid_hkd_return, invalid_period_labels, invalid_currency; missing_timing, ambiguous_timing, invalid_timing_date, invalid_market_timezone, missing_source_name; invalid_price_start_at, invalid_price_end_at, invalid_fx_start_at, invalid_fx_end_at, invalid_available_at; wrong_month_ followed by endpoint field, stale_ followed by endpoint field; inverted_price_times, inverted_fx_times, availability_before_observation, not_available_at_decision. Failed S03-A reason text is retained verbatim, with further failures joined by semicolons. Report adds window_start_history_insufficient when the first required period has no return. No listing date inference is made. Valid reason is ok.

## RED/GREEN commands actually run

- Initial `.venv/bin/python -m pytest tests/test_alignment.py -q`: exit 2, collection failed because portfolio.data.alignment did not exist. Tests were written before implementation.
- After first implementation, same command: 2 failed, 5 passed. Synthetic summer New York observations preceded 21:00 UTC FX; available_at was incorrectly earlier than FX. Corrected synthetic availability to the latest required observation. Duplicate test initially duplicated the extra month outside the window; corrected it to duplicate a required month.
- Initial GREEN: same command, 7 passed.
- Expanded negative/equality/provenance tests: 1 failed, 21 passed because pandas disallowed inserting boolean into a float column; fixed the test fixture to object dtype so core boolean rejection was exercised.
- Expanded GREEN: same command, 22 passed.
- Self-review found an empty requested asset list produced a coverage frame without the declared schema. Added test before correction: same command, 1 failed, 22 passed. Corrected empty coverage schema.
- Final targeted GREEN: `.venv/bin/python -m pytest tests/test_alignment.py -q`, exit 0, **23 passed in 2.25s**.
- Final `PYTHONPATH=src .venv/bin/python scripts/verify_alignment.py`, exit 0: `Synthetic alignment acceptance passed: early 1, late 2 eligible; fixed 60 months.`

Tests cover fixed 60/59 boundaries, early/late availability, missing middle and oldest history, extra history, missing FX, missing and duplicate timing/returns, malformed timezones, stale threshold 7 accepted/8 rejected, wrong month, equality, forged file provenance, explicit DST offsets, invalid returns including bool/nonfinite/<-1, input immutability, stable ordering, and empty matrices/schemas. The script independently expects early counts HKD_COMPLETE=60, USD_COMPLETE=59, others=59; late HKD_COMPLETE=USD_COMPLETE=60, others=59. It asserts eligible IDs, every retained return .01, fixed boundary dates, and original missing_fx_end reason. Files are exported under outputs/acceptance/S03B/synthetic: input reconciliation/timing, early/late report/coverage/matrix, and summary.json.

## Self-review and limitations

Reviewed against the binding spec: no source table mutation, no zero-fill, no older-window fallback, no observed_at substitution, all requested assets reported, deterministic order, original failure evidence retained, and importer metadata wins over uploaded provenance. Currency validation was aligned with the existing S02/S03-A CURRENCIES set. No dependencies or network used.

This verifies declared time rules, not truth of supplied timestamps, vendor revisions, genuine final valuation days, exchange calendars, or actual historical availability. Seven days is an explicit research threshold. Daily automatic aggregation is unsupported and existing S03-A alignment_required remains blocked. Synthetic data is not real product evidence. S03-C and S04+ remain unimplemented; eligible count is not S05 candidate N. Independent review and full-suite integration verification belong to parent task orchestration.

## Root review correction: conservative period maturity

Root audit clarified that the monthly label date must itself have been reached in the declared market calendar, plus UTC for foreign FX, before a full monthly return may qualify. An observation within the seven-day research threshold does not establish that the full period is complete. Implemented `period_not_complete_at_decision` per coverage period when decision local date precedes the return's month-end date; foreign rows additionally require the UTC decision date to reach that date. This is conservative label maturity, not automatic exchange-calendar certification.

Changed the existing seven-day/equality test to retain the January 24 price observation but declare January 31 availability, with decision exactly equal to that availability. Added January 24 full-month regression and explicit New York calendar boundary regression before changing the core.

Actual RED command `.venv/bin/python -m pytest tests/test_alignment.py -q`: exit 1, **2 failed, 23 passed in 2.61s**. Both new tests found a `(1, 1)` matrix where `(1, 0)` was required. After minimal maturity check, same command: exit 0, **25 passed in 2.42s**. Added separate UTC foreign-period boundary case, then final same command: exit 0, **26 passed in 2.63s**. Final `PYTHONPATH=src .venv/bin/python scripts/verify_alignment.py`: exit 0, `Synthetic alignment acceptance passed: early 1, late 2 eligible; fixed 60 months.` The existing early HKD / unavailable USD expectations remain intact. Updated files: alignment.py, test_alignment.py and this report; no UI edits.

## Independent review correction: file-backed physical row identity

Reviewer identified that pandas retains the complete source_rows attrs after slicing; the prior positional lookup could silently attribute a filtered row to the wrong physical source line. File-backed timing now must be the unchanged complete `read_file` frame. The core reparses raw_bytes using source_file/source_sheet, compares frame content/dtypes/column order and original index, and raises `ValueError: file-backed timing must be an unchanged read_file frame; reload the original file` for transformed, filtered, reordered, or reindexed content. An exact copy remains allowed. All physical row and source metadata then come from the reparsed frame, so even changed source_rows attrs cannot override actual lines. The UI supplies the complete upload; callers wanting derived subsets must reload/pass the full frame rather than slice it.

Actual RED `.venv/bin/python -m pytest tests/test_alignment.py -q`: exit 1, **3 failed, 26 passed in 2.96s**. Filtered, reversed/reset-index, and reindexed file-backed frames failed to raise. After fix, same command: exit 0, **29 passed in 2.89s**. Added an additional physical-line regression with a blank CSV line and forged source_rows attrs; a blocked final-period row retains actual physical row 4. Final targeted command: exit 0, **30 passed in 2.66s**. Final `PYTHONPATH=src .venv/bin/python scripts/verify_alignment.py`: exit 0, `Synthetic alignment acceptance passed: early 1, late 2 eligible; fixed 60 months.` No UI or unrelated task files changed.

Also verified XLSX with a non-first named timing sheet: complete frame accepted, original sheet `timing` and physical row 3 retained despite forged source_rows attrs; filtered/reset-index XLSX rejected. Latest final targeted command `.venv/bin/python -m pytest tests/test_alignment.py -q`: exit 0, **31 passed in 3.49s**. Acceptance script rerun: exit 0 with unchanged early1/late2 message. Both CSV and XLSX provenance are sourced from reparsed read_file metadata.
