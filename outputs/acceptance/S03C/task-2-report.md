# S03-C Task 2 implementation report

Implemented the independent 港币利率查验 Streamlit page. Task 2 implementation is ready for independent review; controller owns final review, full-suite/package checks and real-browser acceptance.

## Files and behavior

- `app/views/risk_free.py`: native widgets and existing styles; exact specified keys, defaults, case labels and button/download labels. Calls Task 1 APIs without computing financial formulas. Sidebar/default routing remains in `app/main.py`.
- `tests/test_risk_free_view.py`: 14 AppTests covering default data-import landing and navigation, exact complete series, four failed cases, longer/missing windows, decision immaturity, malformed parameters, no-upload disabled action, input invalidation and result-download removal, CSV provenance, filename/bytes changes, non-first XLSX sheet, malformed workbook/CSV, decimal result CSV, bundle isolation and Chinese summary values.
- `app/views/hkd_returns.py`, `app/views/alignment.py`: only warning text updated to direct users to the separate proxy page, retaining limits on portfolio estimation, Sharpe, backtesting and real-source certification.

The page exposes SYNTH/method/credit-risk limitations prominently; Chinese summary displays period days, annual quote percent and monthly return percent. Missing selected quote displays 未知年化报价. Complete evidence keeps technical reason codes and original decimal returns. Two result downloads appear only for the current completed computation; template/sample downloads are separate. Fingerprints include mode, case, parameters, synthetic content, file bytes/name and selected sheet. Old results are cleared before parsing changed uploads/sheets and before computation; parsing/computation errors cannot retain stale output.

The user-facing convention expander uses concise Chinese method/input/time/source guidance with official HKMA/TMA links, rather than developer API or test documentation.

## TDD evidence and exact commands

1. Before production changes:
   `.venv/bin/python -m pytest tests/test_risk_free_view.py -q > outputs/acceptance/S03C/task-2-red.txt 2>&1`
   Exit 1: **14 failed in 1.89s**, expected missing sidebar feature assertions. Output saved in `task-2-red.txt`.
2. After initial implementation: same focused test command targeting `task-2-green.txt`; **14 passed in 2.13s**.
3. After requested summary inspectability enhancement, updated assertions first:
   `.venv/bin/python -m pytest tests/test_risk_free_view.py -q > outputs/acceptance/S03C/task-2-summary-red.txt 2>&1`
   Exit 1: **2 failed, 12 passed in 1.94s**, expected missing Chinese summary columns.
4. Final focused verification:
   `.venv/bin/python -m pytest tests/test_risk_free_view.py -q > outputs/acceptance/S03C/task-2-green.txt 2>&1`
   Exit 0: **14 passed in 2.15s**.
5. Existing page regression verification:
   `.venv/bin/python -m pytest tests/test_hkd_returns_view.py tests/test_alignment_view.py -q > outputs/acceptance/S03C/task-2-existing-views.txt 2>&1`
   Exit 0: **16 passed in 5.00s**. Subsequent changes were confined to the new page and its tests.

## Self-review and limits

Reviewed scope against Task 2 brief and design: no core changes, bundle writes, network access, global CSS, dependency installation, Git initialization or commits. Summary uses values supplied by the core; no formula duplication. Core availability remains a declaration check, not source certification. Sample defaults match exact acceptance values. All result errors reset session result and hide output/downloads.

AppTest uploads use a monkeypatched Streamlit file_uploader with real file bytes and the actual parser/core; this proves parsing/state behavior, **not native browser upload interaction**. Controller must separately inspect actual browser complete/failed states, changed-input removal and 1440/720 layouts. Full suite and package reinstall are controller-owned. Independent review remains required before Task 2 is marked complete.
