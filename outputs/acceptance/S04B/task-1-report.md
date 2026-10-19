# Task 1 implementation report

Status: DONE_WITH_CONCERNS (awaiting independent review).

Implemented the fixed five-dataset reference catalog, strict pre-I/O plans, curl transport with explicit timeout/TLS/redirect controls, French bounded in-memory ZIP handling and official member identity, model-specific monthly tables, HKMA monotonic pagination, raw evidence before parsing/status checks, cooperative cancellation, immutable schema 2 publication, and verified offline reading. S01 imports retain parser compatibility; Yahoo schema 1 retains existing tests. Shared `_verified_entries` handles artifact integrity for both schemas. HKMA rejects oversized pages and records response retrieval time, without claiming historical availability.

## TDD evidence

RED command: `.venv/bin/python -m pytest tests/test_reference_updates.py -q`

Saved to `task-1-red.log`: collection error `ModuleNotFoundError: No module named 'portfolio.data.reference_updates'`, expected because the new API did not exist before implementation. Initial tests exercised full archives, real parsers, real published files, and injected RawResponse transport boundaries.

GREEN command: `.venv/bin/python -m pytest tests/test_reference_updates.py tests/test_source_probe.py tests/test_updates.py -q`

Saved to `task-1-green.log`: **94 passed in 1.37s**. Follow-up edge tests added invalid plans, cancellation after response, missing months, FF5 scaling, bad archives, region mismatch, malformed HKMA records, ignored datasize, oversized pages, local error propagation, and manifest corruption/identity/path/file checks.

## Files changed

- `src/portfolio/data/providers/french.py`
- `src/portfolio/data/providers/hkma.py`
- `src/portfolio/data/reference_updates.py`
- `src/portfolio/data/snapshots.py`
- `scripts/probe_sources.py`
- `tests/test_reference_updates.py`

## Self-review and concerns

- No live downloads, new dependencies, UI changes, controller script edits, Git operations, or credential/exception text persistence.
- French legacy parser rejects internal gaps by default; the new adapter explicitly permits them so requested missing months become partial diagnostics.
- HKMA validates actual positive finite observations and rejects invalid values as unavailable parse_error; it does not fill missing USD observations.
- Partial/cancelled tables are diagnostic only; schema 2 has no import_file.
- The new adapter is deliberately synchronous; cancellation cannot interrupt a request already in flight.
- Initial RED was a missing-module collection failure; additional edge cases were added after implementation, so those additional tests were not individually demonstrated RED. Independent review should examine the dense snapshot field validation and malformed-input coverage before final acceptance.
- Full suite and online evidence remain controller responsibilities per task scope.

## Controller review amendment

Controller found that a French schema mismatch could leave the full-history candidate in diagnostic `table`, making a failed snapshot unreadable because dates were outside the plan. Added `test_wrong_model_full_history_never_publishes_outside_plan_table` first. RED command `.venv/bin/python -m pytest tests/test_reference_updates.py::test_wrong_model_full_history_never_publishes_outside_plan_table -q` failed with `ValueError: invalid observation date` (saved `task-1-regression-red.log`). Kept parsed candidate local until model schema and requested filter validate. Re-ran the focused three-file command: **95 passed in 1.37s** (latest exact runtime in `task-1-green.log`).

## Independent review fixes

Added reference-only transport classification: timeout stays separate, curl TLS/certificate codes (including 35 and 60) and SSLError map to `tls_error`, all other expected transport errors map to `transport_error`. Yahoo's helper remains unchanged. Future reference writes now identify `reference-v2`; schema2 continues to load reference-v1. Original online artifacts were not opened for writing or regenerated, and no live requests were made.

Schema2 created_utc/retrieved_utc now require timezone-aware timestamps with a zero UTC offset. Expanded touched cancellation/error transitions and timestamp validation into explicit blocks.

RED command: `.venv/bin/python -m pytest tests/test_reference_updates.py -q`; `task-1-review-red.log` records **6 failed, 37 passed**: both TLS35/60 assertions and four naive/nonzero-offset timestamp mutations failed as expected. Generic curl7 and timeout28 already passed as compatibility guards.

GREEN command: `.venv/bin/python -m pytest tests/test_reference_updates.py tests/test_source_probe.py tests/test_updates.py -q`; `task-1-review-green.log` records **104 passed** (exact runtime retained in log). Includes SSLError without a code, future writer version, and legacy v1 adapter read. No exception text is persisted. Review fixes complete; awaiting re-review.
