# S03-B Implementation Plan

> **For agentic workers:** Use superpowers:subagent-driven-development task by task with review gates. User authorized this next staged deliverable. No Git repository exists; record file diffs and evidence instead of commits/worktrees.

**Goal:** Deliver an inspectable fixed monthly window with explicit cross-market availability evidence.
**Architecture:** Independent alignment core consumes S03-A reconciliation; Streamlit supplies inputs and displays results. Synthetic acceptance runs the real S03-A conversion first.
**Tech Stack:** Existing pandas, Python, pytest, Streamlit; no new dependency or network download.

## Global Constraints

Binding spec: `docs/superpowers/specs/2026-10-13-s03b-alignment-design.md`.
Use fixed 60 months by default; no zero filling, older-window fallback, or mutation of source tables. HKD decimal returns. Time evidence is declared, not independently certified. S03-C and S04+ remain unimplemented. S02 schema unchanged. No Git initialization.

### Task 1: Alignment core and reproducible scenarios

Files: create `src/portfolio/data/alignment.py`, `src/portfolio/data/alignment_samples.py`, `tests/test_alignment.py`, `scripts/verify_alignment.py`.

Interfaces: `align_monthly(reconciliation, timing, *, asset_ids, end_month, decision_at, months=60) -> AlignmentResult`; fields report, coverage, matrix, window_start, window_end, decision_at. report columns asset_id,status,valid_months,missing_months,reason; coverage at least asset_id,date,status,reason,hkd_return with retained reconciliation and timing evidence. `TIMING_FIELDS` exports upload columns. `sample_alignment_inputs()` returns `(reconciliation, timing, asset_ids)` via real `reconcile_hkd` with synthetic monthly inputs.

- [x] Write meaningful failing tests for boundaries, future data, missing/ambiguous inputs, invalid timing and evidence provenance. Verify RED with `.venv/bin/python -m pytest tests/test_alignment.py -q`.
- [x] Implement the core and synthetic sample per binding spec; validate strict end_month/aware decision/positive integer months, reject future requested months, keep deterministic fixed matrix and detailed reasons.
- [x] Run targeted tests GREEN and self-review, report actual commands and outcomes in `outputs/acceptance/S03B/task-1-report.md`.
- [x] Implement offline `scripts/verify_alignment.py --output ...` with independent expected reports (early HKD only, late HKD and USD; others excluded), export input evidence and both matrices/reports/coverage/summary. Verify with `PYTHONPATH=src .venv/bin/python scripts/verify_alignment.py`.
- [x] Independent spec/quality review; resolve important findings before task 2.

### Task 2: Inspectable Streamlit page, regression and records

Files: create `app/views/alignment.py`, `tests/test_alignment_view.py`; modify `app/main.py`, `app/views/hkd_returns.py`, README and workflow status. Preserve old page semantics.

Consumes Task 1 interface. Add S03-A result origin/content binding so stale source data cannot become alignment input. Page `共同窗口查验`: synthetic or current valid HKD result, explicit end month and Hong Kong decision, timing CSV/XLSX uploader/sheet selector/template, calculate, Chinese summary and coverage/matrix CSV. No calculations duplicated in UI. Use isolated keys prefixed alignment_. All parameter/content changes invalidate result and downloads.

- [x] Write AppTest failures for default navigation, early/late synthetic results, changed inputs invalidation, no-data guidance, malformed upload and current HKD handoff.
- [x] Implement UI consistent with existing styles; update S03-A warning so it refers to separate S03-B checks and remaining S03-C.
- [x] Run `.venv/bin/python -m pytest tests/test_alignment_view.py tests/test_hkd_returns_view.py -q`; record RED/GREEN and self-review in `outputs/acceptance/S03B/task-2-report.md`.
- [x] Independent review and resolve findings; run full pytest once changes stabilize, acceptance script and runtime check.
- [x] Update `outputs/acceptance/S03B/README.md`, `checks.txt`, progress ledger and root/workflow status from actual evidence. Provide concrete user steps and expected asset/month counts; state visual checks actually performed.
