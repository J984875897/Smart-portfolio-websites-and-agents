# S03-B independent final review

**Mode:** PR Review  
**Scope:** Binding S03-B design and Task 2 brief; prior review/report evidence; immutable `final-code.diff` (eight related code/test/script files); current alignment core, sample, acceptance script, Streamlit integration and tests; relevant existing importer/return/fingerprint boundaries and timing documentation. Review prioritizes high-risk integration paths in this substantial diff.  
**Health Score:** 100/100  
**Spec-compliance verdict:** Approved for S03-B's implemented declared-timing and fixed-window contract. No unresolved material compliance finding was identified.  
**Code-quality verdict:** Approved for this local staged deliverable. No material correctness, dependency or maintainability defect was identified in the reviewed scope.

## Findings

No new findings. The prior core maturity/provenance fixes and UI handoff/name fixes were inspected again rather than accepted solely from previous approvals. The separate [focused Task 2 re-review](task-2-rereview.md) records closure and an independently run three-test check.

## Spec and integration evidence

| Requirement / risk | Current evidence |
| --- | --- |
| Fixed shared window, no lookback substitution or fill | `src/portfolio/data/alignment.py:44–45,73–87,119–125` builds the exact requested consecutive month labels and only emits a matrix column when every period passes. No older-window search or fill occurs. Empty eligibility retains the fixed date index; requested assets without observations remain excluded in the report. Asset IDs are sorted. |
| Completed periods and no future observations | Core lines 37–40 compare the end month with the Hong Kong decision month; lines 92–116 require the market-local period-end date, independent UTC period maturity for foreign FX, aware endpoint timestamps in the correct endpoint months, seven-day staleness, ordered observations, and availability no earlier than any required observation and no later than the decision. Equality is accepted. This implements the explicit day-level maturity contract. |
| Valid upstream returns and duplicate rejection | Core lines 76–89 require exactly one return, `status=valid`, a finite decimal HKD return at least −1, accurate adjacent month-end labels, and a known currency. Ambiguous valid/blocked duplicates block the month while their complete original records remain in `reconciliation_evidence`. Original S03-A failure reasons remain in blocked single-row coverage. |
| Source evidence | Core lines 53–71 reparse file-backed timing and reject transformed frames before obtaining authoritative filename, sheet, physical row and SHA-256. Uploaded same-name columns cannot replace those fields. CSV blank-line and XLSX non-first-sheet tests check physical evidence; duplicate timing is retained and blocks acceptance. |
| Derived results and isolation | The core reads source frames and derives new report/coverage/matrix tables. Input-immutability tests cover reconciliation and timing. The artificial fixture runs real `reconcile_hkd` conversion and is never committed to the saved bundle. It deliberately demonstrates complete HKD/USD, middle gap, 59-month history and missing endpoint FX. |
| Current-source handoff | `app/views/hkd_returns.py:172–175` stores source/input origin; `app/views/alignment.py:42–62` verifies usable upstream data, bundle assets/observations/provenance fingerprint and current upstream input fingerprint. Mixed blocked assets and saved assets with no observations remain inspectable. |
| Invalidation and mode correctness | Alignment lines 39,55,68–97 bind actual synthetic content or live reconciliation/origin plus mode, end month, decision, timing source, uploaded bytes/name and sheet. Changes or read errors clear results; result downloads render only under the matching successful token. Explicit mode-specific timing assignment fixes browser restoration without overriding same-mode user choices. |
| Inspectability | The page supplies a compact Chinese asset summary, monthly status, explicitly unusable blocked raw values, full original evidence and report/coverage/matrix downloads in decimal returns. Saved names are retained. Timing templates/help explain availability, revisions, asynchronous valuations and provenance. Navigation defaults to data import. |
| Scope and honest limits | UI/help identify synthetic data, distinguish eligibility from S05 candidate N, disclose the declared rather than independently certified availability evidence, and state that S03-C is pending. Daily automatic aggregation, exchange-calendar certification, risk-free proxy, portfolio estimates and backtests are outside this deliverable. |

## Code and test assessment

The alignment policy remains in the independent core; Streamlit supplies parameters and presents results. Its dependency on the existing importer is narrowly for authentic file parsing/provenance, with no network or UI dependency. The eight changed files serve one feature and its verification; the diff is substantial, so review effort concentrated on time boundaries, provenance and state transitions. The long core routine follows one asset-by-month validation pipeline with explicit reason accumulation; no speculative framework or duplicate UI calculation was introduced.

The test changes exercise real conversion/core results, source immutability, timing boundaries, malformed inputs, provenance and UI invalidation/download contents. Upload and browser-restoration seams use focused monkeypatches while still asserting resulting behavior. Core, AppTest and browser acceptance have distinct purposes; AppTest alone cannot establish actual frontend restoration or visual layout correctness.

## Independent verification and limits

This reviewer independently ran the three focused fix regressions: **3 passed in 1.36s**. A separate read-only Python probe passed real zero and −100% returns, mixed valid/blocked duplicate rejection with both original records retained, exact availability equality acceptance and rejection one microsecond before availability. All six complete new-file sections in `final-code.diff` exactly match current files; navigation and minimal S03-A hunks were checked against current code. Reviewed final diff SHA-256: `9483b483f7b6a3a9e48670649fe8e5650c35c1450490e763012f0d45d74c9ea9`.

The parent owns fresh full-suite, synthetic script, runtime, live Chrome early1/late2, and narrow-layout acceptance checks. This report does not claim those were run by this reviewer, and it does not independently certify a supplier's valuation, publication or revision history. No production or test file was modified during review.

## Summary

The reviewed S03-B code satisfies the fixed-window and declared-timing contract with no remaining material finding. Final acceptance should attach the parent's fresh executable and browser evidence; S03 overall remains incomplete until S03-C is delivered.
