# S03A independent final review

Date: 2026-10-13. Mode: PR Review. Scope: S03A core, Streamlit integration, synthetic fixtures, acceptance command and tests in `final_review.diff`, checked against the S03A design and implementation plan. No Git repository; the supplied before/after diff and actual files were reviewed. No implementation files were modified and no full suite was rerun by this reviewer.

## Specification verdict

**Task 1: Approved.** Local total returns and confirmed adjusted-price returns follow the stated monthly calendar-end convention. Duplicate asset-month observations, invalid predecessors, missing months, unsupported inputs and unconfirmed adjustment are blocked. Foreign-currency conversion uses exact endpoint dates; missing or invalid FX produces NaN with reasons. HKD returns do not require FX. Zero and total loss remain valid. Inputs remain separate from derived results, and there is no extra dividend addition.

**Task 2: Approved.** The original data-import page remains the default. Synthetic data is isolated from the saved S02 bundle. Confirmation, data content and FX file bytes/worksheet participate in result invalidation; read and calculation failures clear previous results. The Chinese summary displays percentages without changing the core decimal outputs. Source tables and current-result CSV downloads remain available. S03B/C limitations remain visible.

**Task 3 calculation, evidence and delivery documentation: Approved.** `scripts/verify_hkd.py` imports fixtures through the real S02 pipeline, asserts independent expected results, checks decomposition and unchanged observations, exercises missing FX/unconfirmed adjustment/ordinary-price failures, and writes the specified CSV and JSON artifacts with input hashes. The subprocess test checks the actual command and resulting files.

**S03A delivery approved.** The completed acceptance README and checks, root README and development workflow now accurately describe the synthetic calculation, UI procedure, reproduction commands and verification limits. The workflow preserves the unfinished overall S03 checkboxes and explicitly defers S03B/C. Browser evidence records successful navigation/calculation and HTTP/health responses of 200. Independent inspection of the 1440/720 screenshots found readable controls and warnings without visible overlap; the result screenshot shows USD 2.294872%, native HKD 1%, valid zero/total-loss cases and blocked unconfirmed adjusted-price rows. Native browser upload/download dialogs remain explicitly outside the exercised browser coverage. Progress and implementation checklists can now record this completed review; this approval does not authorize S03B/C or later stages.

## Quality verdict and findings

**Implementation approved. No unresolved Critical, Important or Minor code findings.** Calculation policy stays in the core; the UI is presentation and state handling. Tests exercise real imports and calculations, with file-uploader substitution confined to the browser boundary. The new display conversion preserves NaN and does not duplicate the financial formula.

### Original Important finding: resolved

Previously, `validate_fx` allowed submitted `source_file`, `source_sheet`, `source_row` and `source_hash` columns to override actual uploaded-file metadata. The authoritative assignment at `src/portfolio/data/fx.py:41` now overwrites those fields for file-backed frames using attributes, physical rows and the SHA-256 of actual bytes. In-memory caller evidence retains its separate supported behavior.

`tests/test_fx.py:83` covers CSV and XLSX with stale submitted provenance, including CSV blank-line physical rows, worksheet names, duplicate-evidence dictionaries, reconciliation fields and unchanged input frames. The independent original reproduction now returns `actual.csv`, physical row 2 and the real byte hash instead of `old.csv`, row 999 and `old-hash`.

## Verification reviewed

- `fix_report.md`: actual red evidence for both file-provenance regressions, followed by 33 passing core tests.
- Updated `ui_report.md` and `ui_green.txt`: 20 passing S03A/S02 UI tests, including the visible Chinese percentage summary and missing-FX NaN state.
- `full_tests.txt`: **132 passed in 14.70s**, produced by the main agent's full-suite run.
- `verification.txt`: five valid synthetic HKD rows; USD 1% with 7.8 to 7.9 FX gives **2.294871794872%**; missing FX is blocked while native HKD remains 1%.
- Independent read-only probes: all four summary input hashes match fixture bytes; all five valid artifact rows satisfy the local/FX/cross-term decomposition within `1e-12`; both USD endpoint hashes match the actual FX fixture; the original provenance reproduction is fixed.
- Documentation closure: read `outputs/acceptance/S03A/README.md`, `checks.txt`, updated root README and workflow; inspected `browser_checks.json`, `browser_1440.png`, `browser_720.png` and `browser_result.png`. No implementation changes occurred after the 132-test run.

No claim is made that these synthetic checks establish market information availability, the 60-month common window, a risk-free proxy, candidate qualification or investment performance. Those remain outside S03A.
