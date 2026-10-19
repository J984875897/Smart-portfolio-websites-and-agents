### Spec Compliance

- ✅ The calculation, output schema, fixed window, timing checks, synthetic cases, independent acceptance script and convention documentation match Task 1. Evidence: `src/portfolio/data/risk_free.py:12-93`, `src/portfolio/data/risk_free_samples.py:4-17`, `scripts/verify_risk_free.py:15-36`, `docs/data/risk_free_convention.md:3-33`.
- ⚠️ Minor test-spec gap: the brief explicitly requests directly constructed minimal frames for boundary testing; boundary tests currently modify the shared sample factory instead (`tests/test_risk_free.py:35-64`). This does not expose a calculation defect, but leaves those tests coupled to sample generation.
- ⚠️ Test-first chronology and saved command outcomes cannot be independently established from the source diff; the controller should retain the reported RED/GREEN artifacts. UI requirements belong to subsequent tasks and were not assessed here.

### Strengths

- `src/portfolio/data/risk_free.py:55-93`: each requested month remains present, ambiguity and missing evidence block returns, and maturity/availability failures retain NaN rather than manufacturing usable cash returns.
- `src/portfolio/data/risk_free.py:37-53`: file-backed values and index are checked against a fresh parse; trusted physical rows come from that parse, while ordinary frames receive an explicitly generated CSV identity.
- `scripts/verify_risk_free.py:19-28`: Decimal-based expected values independently check annual-percent conversion and blocked-month NaNs; the script also checks source immutability and immature March (`:18`, `:34-36`).
- `docs/data/risk_free_convention.md:9-33`: declared timing, research staleness, failure codes, bank credit/liquidity risk and calendar-month accrual approximation are explicit. The code adds no downloader, USD substitution, Sharpe calculation or cash investment behavior.

### Issues

#### Critical (Must Fix)

- None.

#### Important (Should Fix)

- None.

#### Minor (Nice to Have)

- `tests/test_risk_free.py:35-64`: invalid-row and timing-boundary tests use `sample_risk_free_quotes()` rather than the brief's directly constructed minimal frames. Add a small independent one-row frame for exact observation/availability/start boundaries and invalid metadata; this prevents future sample-factory changes from obscuring core contract regressions.

### Assessment

**Spec compliance:** Approved with a minor test-spec gap.

**Task quality:** Approved.

**Reasoning:** The implementation fails closed, preserves fixed monthly identity and evidence, and independently checks the main financial conversion. No correctness or maintainability issue warrants blocking this task; an independent minimal boundary fixture would improve the requested test isolation.

**Focused outside-diff checks:** Inspected `alignment.py:22-29` and `returns.py:12-29` for the concrete risk that reused parsers accept naive timestamps, non-strict dates or invalid quotes; the helpers reject those cases. Inspected `importer.py:17-52` for the concrete risk that reparsing preserves caller-forged physical rows; fresh CSV parsing regenerates row numbers, and XLSX parsing resolves the selected sheet. No tests were rerun because inspection raised no unresolved behavioral doubt.
