# S03-C HKD Cash Proxy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Deliver an inspectable monthly HKD cash-return proxy with conservative availability checks.

**Architecture:** Pure pandas calculation in portfolio.data.risk_free; separate synthetic input factory and Streamlit view. No S02 schema mutation or network downloads. Two sequential deliverables with independent review gates.

**Tech Stack:** Existing Python 3.14 venv, pandas, pytest, Streamlit AppTest, openpyxl; no new dependencies.

## Global Constraints

Full requirements: `docs/superpowers/specs/2026-10-16-s03c-risk-free-design.md`. Scope S03-C only. HKD decimal monthly output; never substitute USD RF or fill missing with zero. HIBOR is an explicitly approximate cash proxy with bank credit risk, not a tradeable risk-free holding. Declared availability is not historical source certification. No Git repo: preserve baseline snapshot and diff artifacts, do not initialize Git or commit. Baseline 172 tests must remain passing.

### Task 1: Pure calculation, synthetic data and independent acceptance

**Files:** Create `src/portfolio/data/risk_free.py`, `src/portfolio/data/risk_free_samples.py`, `tests/test_risk_free.py`, `scripts/verify_risk_free.py`, `docs/data/risk_free_convention.md`. Acceptance artifacts under `outputs/acceptance/S03C/`.

**Interfaces:** `risk_free_monthly(quotes: pd.DataFrame, *, end_month: str, decision_at: str, months: int=60) -> RiskFreeResult`. Dataclass fields exactly `report,series,available,window_start,window_end,decision_at,currency='HKD',frequency='monthly',proxy_method='hibor_1m_simple_act365f'`. `sample_risk_free_quotes(case='完整报价') -> pd.DataFrame`, case values exactly `完整报价`, `缺中间报价`, `月中报价`, `版本晚可得`, `USD报价`. Factory provides selected monthly rows for Jan–Mar2024, 3.65% annual, explicitly SYNTH source. Complete quote_at dates Dec29/Jan31/Feb29 at11:15+08; available_at at12:15 same dates. Failurecases remove February, set Febquote Feb1, set Febavailability Feb1, set FebcurrencyUSD respectively.

- [x] Write tests first against spec. Primary check:
```python
def test_percent_quote_to_monthly_decimal():
    q = sample_risk_free_quotes()
    result = risk_free_monthly(q, end_month='2024-03', decision_at='2024-03-31T16:00:00+08:00', months=3)
    assert result.available
    assert result.series.tolist() == pytest.approx([.0031,.0029,.0031])
    assert result.report.days.tolist() == [31,29,31]
```
Also directly construct minimal frames for spec boundaries, invalid metadata, missing and ambiguous months, full fixed 60-month series (no older replacement), negative/zero, malformed rows/timestamps and unchanged CSV/XLSX provenance, reordering/immutability. Keep failure codes stable/descriptive and documented. Model error reporting after alignment.py, but do not change that module.
- [x] Run `.venv/bin/python -m pytest tests/test_risk_free.py -q` and save missing-feature RED output to acceptance directory before production code. Implement pure module and factory, then run GREEN focused suite and affected existing tests.
- [x] Implement acceptance script, importing from local src as existing verify scripts do. It writes synthetic inputs, report.csv, rf_hkd.csv and summary.json for every case under S03C/synthetic. Independently assert 31/29-day results with Decimal literals, blocked month stays NaN in series/report, no source mutation, and immature decision blocks March. Script prints a concise pass message, exits nonzero on assertion failure.
- [x] Document exact input columns, allowed metadata and units, period/availability/staleness rules, formula, failure codes, source links and proxy caveats in risk_free_convention.md. Run script and focused tests; report exact commands, output, changed files, self-review and risks in task-1-report.md. Mark checklist only after reviewer approval.

### Task 2: Inspectable Streamlit page and UI verification

**Files:** Create `app/views/risk_free.py`, `tests/test_risk_free_view.py`; modify `app/main.py`. Minimal scope corrections to warning text in `app/views/hkd_returns.py` and `app/views/alignment.py` so they direct users to separate interest-rate checks without implying portfolio/retest completed. Do not change upstream calculations.

**Interfaces:** Consume Task1 APIs verbatim. `render()` exposed for main.py. Sidebar option exactly `港币利率查验`; default remains existing data page. Keys `rf_mode` radio (`人工测试案例`,`上传报价文件`), `rf_case` selectbox (Task1 case names), `rf_end` text default2024-03, `rf_months` integer number_input default3 range1–600, `rf_decision` text default2024-03-31T16:00:00+08:00, `rf_upload`, `rf_sheet`, `rf_compute` button label `查验港币利率代理`, `rf_result` storedresult orNone. Decision UI explicitly requires +08:00 as existing pages do. End/months are editable; sample only covers3 months so longer windows visibly unavailable. Summary includes `可用月份 3 / 3` or `可用月份 2 / 3` and series status. Render rf_hkd as percent in Chinese summary; original decimal stays in evidence/download.

- [x] Write AppTest before implementation. Exercise default page still data import, navigation, artificial complete exact series, 4failedcases, missing windows, decision immaturity, result and downloads removed when any input changes, invalid decision/format, no upload disables compute, CSV file parsing, XLSX nonfirstsheet, malformed upload no stale result, sample isolation from bundle. Uploads can be injected by monkeypatching Streamlit file_uploader as existing test_alignment_view does; do not claim native upload proven by this test.
```python
at.radio(key='workspace').set_value('港币利率查验').run()
at.button(key='rf_compute').click().run()
assert at.session_state['rf_result'].series.tolist() == pytest.approx([.0031,.0029,.0031])
at.selectbox(key='rf_case').set_value('缺中间报价').run()
assert at.session_state['rf_result'] is None
```
- [x] Save RED missing-feature output, implement view and navigation using native widgets/current styles. Keep UI formula-free. Track fingerprint from all relevant inputs (mode,case,params,file bytes/name,sheet), clear result before attempting parsing/computation; no silent replay of old results. Catch input ValueError and supported file exceptions, show errors. Template/sample download is separate from two result downloads with labels `下载利率查验报告 CSV` and `下载港币代理收益 CSV`; result downloads exist only for current completed computation. Provide full report as expandable evidence; synthetic/method risks prominent.
- [x] Run `.venv/bin/python -m pytest tests/test_risk_free_view.py -q`, then existing view tests. Update minimal upstream warning text to say monthly conversion/time checks alone are insufficient and separate proxy is available; no claim of full source certification or Sharpe. Record self-review, RED/GREEN commands/output in task-2-report.md. Independent review required before marking complete.

## Final verification and user handoff (controller)

- [x] Run full pytest and verify_risk_free.py, reinstall package without network/dependencies for local app imports.
- [x] Inspect real browser complete/failed sample and changed-input clearing; widths1440/720 no page overflow or icon overlap. Save screenshots and browser checks. If real browser unavailable, explicitly report that limitation rather than substitute AppTest claim.
- [x] Generate final code diff vs baseline snapshot for independent final reviewer. Resolve all important findings with covering tests and re-review.
- [x] Update root README, S03 workflow checkboxes/status and S03C acceptance README/progress/checks. Distinguish month-only S03 acceptance from remaining real data limitations. Next step S04 only after user instruction.
