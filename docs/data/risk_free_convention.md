# HKD monthly cash proxy convention

`risk_free_monthly(quotes, *, end_month, decision_at, months=60)` returns a `RiskFreeResult` with fields `report, series, available, window_start, window_end, decision_at, currency='HKD', frequency='monthly', proxy_method='hibor_1m_simple_act365f'`.

Required columns are `date, quote_at, available_at, quote_percent, currency, benchmark, tenor, day_count, compounding, source_name`. Metadata must be exactly `HKD, HKAB_HIBOR, 1M, ACT/365F, simple`; source_name is a nonblank string. `quote_percent` is explicitly an annual percentage: 3.65 means 3.65% per annum, while 0.0365 means 0.0365% per annum. Finite numeric strings support CSV imports; booleans, NaN and infinity are invalid. Zero and negative quotations are accepted, provided the resulting return is finite and at least -1.

Each target natural month has exactly one selected quotation, labeled with strict YYYY-MM-DD natural month end. `end_month` is strict YYYY-MM and `months` is a positive integer excluding bool. The output always has exactly that number of month-end rows; older records never replace missing periods. Duplicate records within a calendar month are ambiguous even if one has a non-month-end label. Completely unparseable date rows block the entire requested window because their intended month cannot be safely determined. Well-formed records outside the requested window do not fill gaps.

Both period anchors are natural month ends at 16:00 Asia/Hong_Kong, with the start at the previous month end. `quote_at`, `available_at` and `decision_at` require timezone-aware ISO datetimes containing T. The quote and its current version's latest availability must both be at or before the start anchor. Availability must be at or after observation and at or before decision. Quote age must be no more than exactly 7×24 hours at the start anchor, inclusive. This is a research staleness limit, not a trading calendar or assurance of the latest available fixing. The period end anchor must be at or before decision, inclusive. Unmatured or future periods remain blocked. The importer declares availability of the current version and all its inputs; the software does not infer historical publication from a download date.

The calculation is `rf_hkd = quote_percent / 100 * days / 365`, with actual natural month-end date difference and fixed 365 denominator in leap years. Thus annual 3.65 yields monthly decimals 0.0031 for 31 days and 0.0029 for 29 days. The series has month-end string index named date and name rf_hkd. Report columns include date, start_date, end_date, start_at, end_at, days, status, reason, rf_hkd, quote_evidence, and quote_ prefixed original fields plus source evidence for a unique quote. Blocked returns remain NaN in both outputs. `available` is true only if every period is valid; this is declared-evidence acceptance rather than source authentication.

Failure codes (semicolon-separated, stable):

- `invalid_date`: unparseable date, conservatively blocking the window.
- `missing_quote`, `ambiguous_quote`: zero or multiple selected records for a target month.
- `invalid_period_label`: unique record is not labeled with the target natural month end.
- `invalid_currency`, `invalid_benchmark`, `invalid_tenor`, `invalid_day_count`, `invalid_compounding`: unexpected required metadata.
- `missing_source_name`: blank or non-string declared source.
- `invalid_quote_at`, `invalid_available_at`: missing, malformed or timezone-naive timestamp.
- `quote_after_start`, `availability_after_start`: observation/version unavailable at the start anchor.
- `stale_quote`: observation older than seven days.
- `availability_before_quote`, `not_available_at_decision`: inconsistent or later availability.
- `period_not_complete_at_decision`: end anchor later than decision.
- `invalid_quote_percent`, `invalid_rf_hkd`: invalid annual quote or calculated return.

Duplicate headers, missing columns, invalid parameters and changed file-backed frames raise ValueError. Inputs are never changed. Frames carrying raw_bytes are reparsed with existing read_file, checked for identical complete values and index, and use reparsed file/sheet/physical-row metadata and original-byte SHA256; caller-forged source rows/columns are ignored. Plain DataFrames always use dataframe.csv, generated row numbers and a SHA256 of the complete calculation-input CSV, not external-file certification. Evidence is retained even for blocked rows.

`sample_risk_free_quotes` supports 完整报价, 缺中间报价, 月中报价, 版本晚可得, USD报价. All are SYNTH declarations covering January–March 2024, never historical data. `scripts/verify_risk_free.py` writes independently checked cases under outputs/acceptance/S03C/synthetic. Join future return statistics strictly by matching monthly date, never by position or by filling missing cash returns with zero or USD RF.

Official sources verified 2026-10-16: [HKMA daily interbank rate documentation](https://apidocs.hkma.gov.hk/documentation/market-data-and-statistics/monthly-statistical-bulletin/er-ir/hk-interbank-ir-daily/) describes segment hibor.fixing and ir_1m in percent per annum; [TMA Code section 2.4](https://www.tma.org.hk/PubFile/TMACode.pdf) specifies HKD ACT/365 even in leap years; [HKAB HIBOR](https://www.hkab.hk/en/rates/hibor) describes interbank quotations and publication. HKAB fixing usually publishes on Hong Kong business days at 11:15; this module does not certify historical fixing times.

HIBOR carries unsecured bank credit and liquidity risk. Holding a selected fixing constant over a full natural month is an explicit research approximation, not a true risk-free asset, investable cash holding, realized return or exact deposit maturity. Real deposits differ in start dates, holidays, maturity and available rates. No Sharpe calculation, downloader, source certification or daily aggregation is provided here.
