### Spec Compliance

- ✅ Spec compliant. `app/views/risk_free.py:34–101` supplies the required native inputs, defaults, explicit Hong Kong offset, Task 1 API delegation and input invalidation; `app/views/risk_free.py:106–126` supplies Chinese summary, complete evidence and separate current-result downloads. Authorized quote/day inspectability and Chinese method/schema/source guidance are present at lines 86–92 and 108–112.
- ✅ Scope remains bounded: `app/main.py:12` adds the separate sidebar choice while preserving the default data page; `app/views/hkd_returns.py:99` and `app/views/alignment.py:30` only update caveats. No mathematical formula implementation, bundle/schema changes or S04 behavior appears in this package.
- ⚠️ Cannot verify actual native browser upload behavior, 1440/720 layout, full-suite/package acceptance or upstream core correctness from this task diff. Controller owns those checks; monkeypatched upload tests explicitly establish parser/state behavior only (`tests/test_risk_free_view.py:81–113`).

### Strengths

- `app/views/risk_free.py:55–82,97–104`: invalidation happens before changed-file parsing and before computation, and the fingerprint guards display; file content/name, sheet and all computation parameters participate.
- `app/views/risk_free.py:38,86–92,114,123`: declaration-only availability, bank credit/liquidity risk, synthetic isolation and percent-versus-decimal units remain explicit.
- `tests/test_risk_free_view.py:26–113`: behavioral assertions cover exact sample returns, failed cases, stale download removal, invalid parameters, upload provenance and nonfirst-sheet changes; `tests/test_risk_free_view.py:115–124` checks exported decimal values and dates.

### Issues

- Critical: None.
- Important: None.
- Minor: None identified within task scope.

### Assessment

**Task quality:** Approved.

**Reasoning:** The page delegates financial work to the core, bounds errors and stale state coherently, and tests observable results and download lifecycle. The authorized UX refinements preserve the technical evidence while making the displayed method and quantities inspectable.

### Checks

- Read supplied diff once; did not reread changed files or run Git commands.
- Concrete outside-diff risk check: matched emitted core reason codes/statuses in `src/portfolio/data/risk_free.py:61–89` against the new Chinese mapping; no mismatch found.
- Concrete outside-diff risk check: inspected `app/views/hkd_returns.py:14` for imported `READ_ERRORS`; it includes ValueError and supported workbook/CSV decoding/file exceptions.
- Inspected supplied final test outputs: `outputs/acceptance/S03C/task-2-green.txt` reports 14 passed; `outputs/acceptance/S03C/task-2-existing-views.txt` reports 16 passed, with no warnings. No tests rerun because review raised no unresolved specific doubt.
