### Task 1: Pure calculation, synthetic data and independent acceptance

**Files:** Create `src/portfolio/data/risk_free.py`, `src/portfolio/data/risk_free_samples.py`, `tests/test_risk_free.py`, `scripts/verify_risk_free.py`, `docs/data/risk_free_convention.md`. Acceptance artifacts under `outputs/acceptance/S03C/`.

**Interfaces:** `risk_free_monthly(quotes: pd.DataFrame, *, end_month: str, decision_at: str, months: int=60) -> RiskFreeResult`. Dataclass fields exactly `report,series,available,window_start,window_end,decision_at,currency='HKD',frequency='monthly',proxy_method='hibor_1m_simple_act365f'`. `sample_risk_free_quotes(case='完整报价') -> pd.DataFrame`, case values exactly `完整报价`, `缺中间报价`, `月中报价`, `版本晚可得`, `USD报价`. Factory provides selected monthly rows for Jan–Mar2024, 3.65% annual, explicitly SYNTH source. Complete quote_at dates Dec29/Jan31/Feb29 at11:15+08; available_at at12:15 same dates. Failurecases remove February, set Febquote Feb1, set Febavailability Feb1, set FebcurrencyUSD respectively.

- [ ] Write tests first against spec. Primary check:
```python
def test_percent_quote_to_monthly_decimal():
    q = sample_risk_free_quotes()
    result = risk_free_monthly(q, end_month='2024-03', decision_at='2024-03-31T16:00:00+08:00', months=3)
    assert result.available
    assert result.series.tolist() == pytest.approx([.0031,.0029,.0031])
    assert result.report.days.tolist() == [31,29,31]
```
Also directly construct minimal frames for spec boundaries, invalid metadata, missing and ambiguous months, full fixed 60-month series (no older replacement), negative/zero, malformed rows/timestamps and unchanged CSV/XLSX provenance, reordering/immutability. Keep failure codes stable/descriptive and documented. Model error reporting after alignment.py, but do not change that module.
- [ ] Run `.venv/bin/python -m pytest tests/test_risk_free.py -q` and save missing-feature RED output to acceptance directory before production code. Implement pure module and factory, then run GREEN focused suite and affected existing tests.
- [ ] Implement acceptance script, importing from local src as existing verify scripts do. It writes synthetic inputs, report.csv, rf_hkd.csv and summary.json for every case under S03C/synthetic. Independently assert 31/29-day results with Decimal literals, blocked month stays NaN in series/report, no source mutation, and immature decision blocks March. Script prints a concise pass message, exits nonzero on assertion failure.
- [ ] Document exact input columns, allowed metadata and units, period/availability/staleness rules, formula, failure codes, source links and proxy caveats in risk_free_convention.md. Run script and focused tests; report exact commands, output, changed files, self-review and risks in task-1-report.md. Mark checklist only after reviewer approval.

