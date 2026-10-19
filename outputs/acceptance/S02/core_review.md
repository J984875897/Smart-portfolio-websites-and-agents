# S02 independent core review

Decision: changes required before the core-review gate passes. Four Important correctness findings, no Critical findings. Reviewed the binding brief, complete implementation diff, API/evidence report and current numbered importer source. Ran only small new reproductions using `PYTHONPATH=src .venv/bin/python`; did not repeat the existing suite, install dependencies, access network, or change implementation.

## Important 1 — Within-file listing disagreements do not block every participating row

Location: `src/portfolio/data/importer.py:74`, `:90-94`.

Reproduction: two otherwise valid rows with explicit asset_id `a`, ticker `A`, ETF/equity/monthly, HKEX; first row currency HKD/date 2025-01-31, second USD/date 2025-02-28. Preview statuses are `[valid, blocked]`. The same applies to exchange/share-class/ticker disagreement. Commit keeps the first row and first listing even though the input gives contradictory identities for that ID. Reversing rows changes which identity wins.

The row-level check only blocks the later row; the subsequent asset-ID group check covers classification/frequency but omits listing fields. This violates the explicitly stated rule that within-file listing-ID disagreements block all participating incoming rows.

Remedy: validate asset-ID groups for incompatible listing identity, accounting for explicit permitted ticker aliases, and block all participants before dedup/commit. Test input-order independence and preservation of existing data.

## Important 2 — DataFrame numeric zero is silently converted into missing data

Location: `src/portfolio/data/importer.py:52`.

Reproduction: valid total_return/percent row supplied as a DataFrame with numeric `value=0`. Preview returns NaN, blocked, issue `missing_value`; string `'0'` succeeds. Python truthiness (`source.get(...) or ''`) loses legitimate numeric zeros. This API explicitly accepts DataFrames, and zero returns are normal observations. The same expression also uses truthiness for identifiers and pandas missing values, rather than explicit missing-value handling.

Remedy: normalize scalar missing values explicitly, preserve numeric zero as `0`, and avoid evaluating `pd.NA` as a boolean. Test numeric zero and pandas nullable missing scalars through the DataFrame API as well as the file paths.

## Important 3 — CSV blank lines break original row provenance

Location: `src/portfolio/data/importer.py:21`, `:51-57`.

Reproduction: CSV header at physical row 1, valid observation at row 2, blank row 3, second observation at row 4. Preview reports source rows `[2, 3]`, so the second observation points at the blank line. pandas skips blank lines by default while preview reconstructs row numbers from the compacted frame.

This violates accepted/error row traceability to original file rows. A file that remains rectangular with a first-row header can contain blank lines; the documented header-offset limitation does not exclude this case.

Remedy: preserve source row indices during parsing, or preserve blank records and explicitly handle them; ensure provenance and all quality findings use the retained original indices. Include a blank-line regression. Consider quoted multiline CSV records when defining physical-line versus logical-record row semantics.

## Important 4 — Dedup status overwrites review eligibility and admits unacknowledged metadata

Location: `src/portfolio/data/importer.py:106`, `:129-144`.

Reproduction: fresh bundle, two identical rows with total_return 70 percent, same asset/date and valid metadata. Preview statuses become `[review, duplicate]`. `commit_import(preview)` without acknowledgement returns one asset, zero observations, and provenance `[review_pending, duplicate]`. The unacknowledged duplicate creates the asset/alias and is marked processed even though its representative observation was withheld. The same issue applies to repeated new monthly-collision rows; classification changes on such duplicate rows can also be processed through the duplicate path.

Duplicate is an observation relation, while review is an acceptance condition. Encoding both in one overwritten status loses the acknowledgement requirement. In particular, a within-upload duplicate must not be treated as an already accepted observation merely because it follows another row.

Remedy: track duplicate identity independently of quality eligibility, or tie duplicate handling to an actually accepted representative/prior observation. Without acknowledgement, every row carrying pending review findings must remain pending and must not create assets, aliases or classification changes. With acknowledgement, retain exactly one observation and trace every source row.

## Other assessment

The core respects separation of tool type/economic class, explicit classification override/history, strict numeric/date validation, same-listing alias restrictions, exact dedup keys and preservation of prior bundles by deep copy. Persistence checks required tables, column schemas, content hashes and raw-source hashes and refuses overwrites. The existing focused tests provide useful evidence, but missed interactions across identity grouping, review and dedup.

Minor maintainability note: dense semicolon-packed statements and multiple responsibilities within preview_import make the quality/identity/dedup ordering hard to inspect. After correctness fixes, small named helpers would reduce the risk of acceptance-state regressions. This is not independently a gate blocker.

Preview does not mutate the prior bundle. Config/preview objects remain mutable through nested dictionaries/DataFrames; the API report explicitly documents callers must not mutate config after preview and must commit against the same existing bundle. This review does not elevate those documented API preconditions into an additional blocker. No S03/S04 financial processing or external-provider scope expansion was observed.

# Re-review after first corrections

Reviewed the fix report, updated API report, current importer, all added regression assertions, and actual focused green log ending `29 passed in 0.59s`. Did not rerun the suite.

All four original Important findings are resolved by the reviewed code:

1. Same-ID listing groups validate exchange/currency/share class and incompatible unaliased tickers, blocking every participating row.
2. Explicit scalar missing detection preserves zero and handles pandas nullable values.
3. CSV parser records physical start lines, including blank lines and quoted multiline records, and preview propagates them.
4. `is_duplicate` is independent of review status; acceptance gates metadata changes and observations separately. Both unacknowledged extreme and monthly duplicate paths are now covered.

Original requirement fixes: approved. Overall spec/quality gate: **still changes required**, because the CSV parser replacement introduces the following Important issue.

## Important 5 — Duplicate CSV headers silently choose the last value

Location: `src/portfolio/data/importer.py:24-34` and `:67`.

New reproduction (only this targeted script was executed): CSV header `asset_id,ticker,date,value,value,tool_type,asset_class,exchange,currency,frequency` and row `a,A,2025-01-31,2,9,ETF,equity,HKEX,HKD,monthly`. Identity mapping with `value -> value`, total_return/percent produces `value=0.09`, `status=valid`, and no quality issues. pandas emits only a Python warning: `DataFrame columns are not unique, some columns will be omitted.` The first value column is silently discarded by `to_dict('records')`.

The replaced pandas CSV reader previously provided disambiguated names for duplicate headers. The new parser retains duplicate column labels, making the explicit mapping ambiguous and causing the selected financial value to be chosen implicitly. This is a correctness/data-loss issue, not a formatting preference.

Remedy: reject duplicate header names with an actionable ValueError before constructing/converting records, or assign deterministic unique names exposed for explicit mapping. Apply the same invariant to direct DataFrame inputs to prevent the same silent collapse. A compact regression with differing duplicate value columns should prove that no valid observation can be committed from an unresolved ambiguous mapping.

No other new Important issue found in the changed listing/review/scalar logic. Persistence logic was unchanged. The earlier minor maintainability note remains nonblocking.

## Important 6 — Missing tickers falsely identify distinct explicit asset IDs as one listing

Additional controller-requested narrow reproduction, verified independently. Location: `src/portfolio/data/importer.py:59-62`, `:75-81` (alias/exact-listing matching) and alias insertion in `commit_import`.

Input: two valid price rows with explicit IDs `ISIN_A` and `ISIN_B`, both empty ticker, HKEX/HKD, empty share_class, ETF/equity/monthly, date 2025-01-31 and value10. These IDs are trusted stable identities under the agreed API; ticker is optional when an explicit stable ID is provided.

Same-file preview outputs `ISIN_A valid`, `ISIN_B blocked` with identity_conflict. After importing A alone, commit persists the incomplete alias `(s, HKEX, '', '', HKD) -> ISIN_A`. Importing B separately then outputs a blocked row whose asset_id has been rewritten to ISIN_A, while its conflict issue identifies ISIN_B. Thus missing ticker is being treated as a real shared listing identifier and falsely conflates unrelated products.

Remedy: use exact listing matching/automatic alias lookup only when the required listing identity fields are complete, and never automatically persist incomplete listing aliases. Preserve explicit stable IDs as authoritative when a listing identity cannot be formed. If explicit manual aliases with missing ticker are supported, distinguish that deliberate mapping from an automatically inferred alias rather than silently generating one. Test distinct missing-ticker IDs both in one file and across uploads, then repeat each ID to verify dedup and stable provenance. No other broad review was performed in this pass.

# Final narrow core gate after fixes 5 and 6

**Spec compliance: approved for S02 core. Code quality: approved for S02 core. UI work may proceed.** No unresolved Critical or Important review finding remains.

Reviewed the appended fix report, current CSV/XLSX parsing and DataFrame entry validation, listing identity lookup and alias insertion, new regression test assertions, and actual focused log showing `33 passed in 0.61s`. No suite rerun or additional broad review was performed.

Finding 5 resolved: CSV headers are checked for uniqueness before record construction; original XLSX headers are checked before pandas disambiguation; direct DataFrame columns are checked before conversion to record dictionaries. All reject ambiguity with an actionable ValueError. Regression cases cover differing duplicate value columns in all three input forms.

Finding 6 resolved: automatic matching and alias lookup require nonempty exchange, ticker and currency; commit only records aliases satisfying this condition. Explicit stable IDs without ticker stay distinct. Regression assertions cover same-file import, sequential import, independent repeated uploads, correct provenance IDs, no incomplete aliases and rejection when both stable ID and ticker are absent.

The earlier four resolutions remain intact in the reviewed current code. The prior minor readability note is nonblocking. These approvals apply to the reviewed S02 core within its documented API preconditions and stage scope, not to the upcoming UI implementation.
