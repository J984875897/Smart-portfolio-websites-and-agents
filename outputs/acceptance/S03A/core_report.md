# S03A Task 1 core report

Implemented only the two new core modules and their independent tests. No existing S02 modules, original DataBundle tables or installed dependencies are changed. No Git initialization or commits.

## Interfaces

- `build_local_returns(bundle, *, adjusted_price_assets=()) -> pandas.DataFrame`
- `validate_fx(frame) -> FxValidation(values, issues)`
- `reconcile_hkd(bundle, fx_frame, *, adjusted_price_assets=()) -> HkdResult(local_returns, reconciliation, fx_issues)`

Constants `LOCAL_COLUMNS`, `FX_COLUMNS`, `ISSUE_COLUMNS`, `RECONCILIATION_COLUMNS` define empty and populated table schemas. `FxValidation` and `HkdResult` are dataclasses. Caller inputs are never mutated.

## Fixed columns

Local returns: `asset_id,date,start_date,end_date,currency,value_kind,frequency,value,local_return,start_price,end_price,status,reason,source_file,source_sheet,source_row,source_hash,start_source_file,start_source_sheet,start_source_row,start_source_hash`.

`date`/`end_date` identify the original observation; `value` is the original value. `source_*` identify that observation and `start_source_*` identify a verified adjusted-price predecessor. Start/end price are numeric only where price calculation applies. Original row order is retained; observations and evidence are matched by asset/month identity, never by array position. Missing numeric results are NaN; absent text evidence is empty text.

FX values: `date,currency,hkd_per_unit,source_name,source_file,source_sheet,source_row,source_hash,sources`. `sources` is a list of dictionaries with `source_name,source_file,source_sheet,source_row,source_hash`, retaining every identical valid duplicate record. A representative first source is also available in the scalar fields, but no duplicate evidence is overwritten.

FX issues: `date,currency,hkd_per_unit,source_name,source_file,source_sheet,source_row,source_hash,code,severity,message`. All issues have `severity=blocked`. Missing required columns produce a schemaful issue table. Duplicate column names raise a clear ValueError. File attributes from S02 `read_file` preserve byte hash, file, worksheet and physical source rows; direct DataFrames receive a deterministic content hash and explicit `dataframe.csv` identity.

Reconciliation: all local columns plus `fx_start,fx_end,fx_return,cross_term,hkd_return`; scalar FX evidence `fx_start_source_name,fx_start_source_file,fx_start_source_sheet,fx_start_source_row,fx_start_source_hash` and equivalent `fx_end_*`; complete duplicate evidence `fx_start_sources,fx_end_sources`.

## Status and reason contract

Successful records: `status=valid,reason=ok`. Failures: `status=blocked`, missing return NaN, with a caller-independent snake_case reason. Local reasons include `invalid_date,ambiguous_asset_month,invalid_currency,unknown_asset,ambiguous_asset_metadata,currency_conflict,invalid_frequency,alignment_required,invalid_value,not_total_return,invalid_value_kind,unconfirmed_adjusted_price,first_period,missing_previous_month,invalid_previous_month`. Alignment-required rows use blocked status and `reason=alignment_required` so they cannot accidentally enter downstream estimates. Reconciliation retains local failures, or adds `missing_fx_start`, `missing_fx_end`, `missing_fx_start_and_end`, `nonfinite_hkd_result`.

FX issue codes include `invalid_date,invalid_currency,invalid_quote,missing_source_name,conflicting_quote,invalid_key_record`, or `missing_columns:<names>`; multiple invalid conditions are separated by semicolons. Any invalid record or differing quote blocks every record with that currency/date key. Such keys cannot feed reconciliation even when another row contains a good quote.

## Mathematics and scope

Total-return observations must be finite and at least -1; 0 and -1 remain meaningful. Prices must be finite and positive, confirmed per asset, and contiguous monthly natural month ends. Ambiguous asset-months block every row and cannot serve as adjusted predecessors. Ordinary prices and price returns never become total returns. Supported currency/frequency sets reuse existing S02 quality constants.

Foreign currency uses exact start/end FX dates and `(1 + local_return) * fx_end / fx_start - 1`, with separate FX return and cross term. HKD uses the local return directly, FX scalars 1, and FX return/cross term 0 even when FX input is empty. No filling, inferred currencies, daily alignment, external data, RF or portfolio outputs.

## Actual verification

Initial test-first checks: `core_red.txt` records 25 failures from the missing new modules, establishing that the feature did not exist before implementation. The initial implementation then passed all 25 checks. Five additional independent review checks cover mixed kinds in a single month, invalid predecessor, impossible date, S02 read_file provenance and invalid local return propagation; all pass without further implementation changes.

Final command: `.venv/bin/python -m pytest tests/test_returns.py tests/test_fx.py -q`.
Actual result in `core_green.txt`: **30 passed in 0.29s**.

Independent expected values exercised: 0.01 with 7.8 -> 7.9 gives 0.02294871794871795 HKD; confirmed 100 -> 101 gives 0.01 local; HKD with no FX gives 0.01; missing FX yields NaN with an explicit reason. Tests also cover exact duplicates, conflicting and invalid FX records, finite values, unsupported currencies, unchanged inputs, schemaful empty outputs, missing months, unconfirmed prices, and -100%.

S03A core calculation is independently checkable. This does not establish information availability or complete S03B/C.

## Important review correction: FX file provenance

File-backed FX provenance now takes precedence over submitted source columns. `read_file` raw bytes determine the SHA-256; its file, worksheet, and physical row attributes determine source identity. Truly in-memory frames retain explicit caller evidence. CSV and XLSX regression tests reproduced the stale-provenance defect before the fix: **2 failed, 1 passed, 13 deselected in 0.43s**. CSV coverage includes blank physical lines; XLSX coverage checks the actual worksheet and workbook hash. Both check duplicate evidence, reconciliation, and unchanged inputs. Final actual verification: `.venv/bin/python -m pytest tests/test_returns.py tests/test_fx.py -q` → **33 passed in 0.39s**. See `fix_report.md` for commands and evidence. No new dependencies or commits.
