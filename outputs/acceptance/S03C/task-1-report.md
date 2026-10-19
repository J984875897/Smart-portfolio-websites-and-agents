# S03-C Task 1 implementation report

Implementation is ready for independent review; no plan checklist has been marked approved.

Changed source files: src/portfolio/data/risk_free.py, src/portfolio/data/risk_free_samples.py, tests/test_risk_free.py, scripts/verify_risk_free.py, docs/data/risk_free_convention.md. Acceptance artifacts: task-1-red.txt, task-1-green.txt, task-1-affected.txt, task-1-script.txt and synthetic/{完整报价,缺中间报价,月中报价,版本晚可得,USD报价}/{inputs.csv,report.csv,rf_hkd.csv,summary.json}.

The pure calculation provides the specified dataclass/API, explicit annual-percent conversion, actual natural month-end days and fixed ACT/365 denominator, prior/end month-end Hong Kong 16:00 anchors, inclusive seven-day quote age, current-version availability and maturity checks. Every target month has a fixed row, blocked values stay NaN, and additional older data cannot replace missing months. Metadata, invalid quotes/timestamps and ambiguous monthly rows fail closed. The synthetic factory labels every source SYNTH and isolates each newly created frame. The script independently uses Decimal literals rather than invoking a calculation helper for expected values.

File-backed inputs are reparsed from original bytes via existing read_file; complete values and index must match, and physical provenance uses reparsed metadata rather than caller-supplied row identifiers. Ordinary DataFrame evidence uses dataframe.csv and the hash of the complete input CSV. No upstream module was changed.

Commands and captured outputs:

1. `.venv/bin/python -m pytest tests/test_risk_free.py -q` before production implementation: expected collection failure because portfolio.data.risk_free did not exist. Saved in task-1-red.txt (ModuleNotFoundError, one collection error). This establishes the missing-feature RED; all initial 37 cases were written before production files. Three additional verification cases were added after implementation for full 60-month coverage/no older replacement, late-version reason detail, and changed file values; those are supplemental coverage rather than separately demonstrated RED cycles.
2. `.venv/bin/python -m pytest tests/test_risk_free.py -q`: `40 passed in 0.37s`, saved in task-1-green.txt.
3. `.venv/bin/python -m pytest tests/test_risk_free.py tests/test_alignment.py tests/test_returns.py tests/test_importer.py -q`: `112 passed in 3.28s`, saved in task-1-affected.txt.
4. `.venv/bin/python scripts/verify_risk_free.py`: `PASS: five SYNTH cases, independent Decimal calculation, blocked NaNs, immutable inputs, immature March.`, saved in task-1-script.txt.

Self-review: verified 3.65 annual percent becomes .0031/.0029/.0031, zero/negative/unit handling, exact seven-day boundary, equivalent timezone offsets and anchor equality, period immaturity, malformed rows/metadata, duplicate and missing periods, fixed full 60-month windows, reordering invariance and input preservation, CSV blank physical lines, XLSX nonfirst sheets, forged row attrs, changed values/indices/reordering rejection. The midmonth synthetic case changes only the February quote_at to February 1; its unchanged January availability additionally exposes the contradictory availability-before-quote declaration. Both reasons are preserved.

Risk/limits: Completely unparseable date rows conservatively block all requested periods because no intended month can safely be inferred; this explicit fail-closed choice is documented. Well-formed out-of-window records are ignored for period selection. HIBOR carries bank credit/liquidity risk, the full-calendar-month fixed-rate accrual is an approximation, and declared availability is not source authentication. No historical data, daily calendar certification, Sharpe, cash holding or downloader was added. Full-suite/browser/package verification belongs to the controller's final gate. Existing dependencies were used; no downloads, installations, Git initialization or commits were performed.
