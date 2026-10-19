# S04-C2 Final Review

Mode: PR Review. Scope: the full 1,086-line `final-code.diff`, design, implementation plan, task reports/reviews, current verification evidence, and the directly relevant unchanged parser, snapshot, importer, C1 and S03 implementations. No Git repository or source changes. The review uses the requested code-reviewer template; the large change was read completely, with focused execution only for named uncertainties.

### Strengths

- `src/portfolio/data/daily_hkd.py:68`: financial arithmetic delegates to S03 `reconcile_hkd`; target rows retain C1 blocking, USD confirmation is strict, partial cache sources block, and HKD uses the native fixed-1 path. Same-month/latest-row/duplicate/age checks are explicit.
- `app/views/daily_hkd.py:142`: input invalidation includes source choices, manifests, roots, file bytes/name/sheet, confirmations and policy. Selected caches are reverified on rerender; errors retract results and exports. The appended route preserves existing pages and performs no download or DataBundle save.
- `src/portfolio/data/monthly_cache.py:29` and `src/portfolio/data/daily_hkd.py:97`: the existing C1 cache adapter does provide manifest/run/raw-hash metadata, which the new connector retains. This resolves the task-1 review's scoped uncertainty about price provenance.
- `scripts/verify_daily_hkd.py:35`: FX reference dates and ratios are independently reconstructed from raw JSON; C1 reference prices use its independent audited reference. The real replay retains `source_global_status=partial`, explicitly identifies the imported legacy endpoint scope, and does not insert `source_status=success`. This is the design's explicit legacy replay exception, not an upgrade of a partial cache. Historical eligibility remains false.
- Recorded regression evidence: `full_tests.txt` reports **420 passed, 2 warnings in 29.11s**. Browser evidence records 1440/720 layout checks, a native CSV download, confirmation retraction and missing-FX blocking. Real replay values agree for SPY and 2800.HK. These checks were read, not broadly rerun.

### Issues

#### Critical (Must Fix)

- None found.

#### Important (Should Fix)

1. **Unknown Yahoo observation dates disappear before conservative endpoint validation.**
   - File: `src/portfolio/data/fx_cache.py:28` (after `parse_yahoo_chart` at line 25).
   - Symptom/source: the unchanged Yahoo parser converts a null timestamp to a missing date; the range filter silently removes that row. Thus `_endpoints` never sees the unlocatable observation required to block all USD endpoints. The upstream `audit_price` can still label this raw response `success` when its close values are positive and other rows cover the requested months.
   - Consequence: a hash-valid success snapshot with dates `[2024-12-31, 2025-01-31, null]` and closes `[7.8, 7.9, 8.0]` produces valid USD HKD return `0.11410256410256436`, violating the binding unknown-date policy. It could conceal a quote whose month or ordering cannot be established.
   - Remedy: validate every raw/parsed observation date before range filtering. Reject an unlocatable timestamp at the cache boundary, or preserve its invalid-date diagnostic so the connector blocks every USD endpoint. Add a regression through the cache reader and connector; include a null timestamp in otherwise valid raw evidence.

2. **Yahoo source row numbers refer to sorted output, not the raw response.**
   - File: `src/portfolio/data/fx_cache.py:31`.
   - Symptom/source: `parse_yahoo_chart` sorts dates and resets the index (`src/portfolio/data/providers/yahoo.py:44`); assigning `parsed.index + 1` afterward loses original array positions.
   - Consequence: raw order `[2025-01-31, 2024-12-31]` is accepted with upstream status success, but the exported rows claim December is raw row 1 and January raw row 2; the actual positions are the opposite. Numerical output remains correct while the promised original-row audit trail is false.
   - Remedy: retain original raw array ordinals before sorting/filtering and associate them using validated unique timestamps/dates, or explicitly reject unordered source timestamps. Add a regression with reordered observations and verify the endpoint's row against the hashed raw JSON.

3. **The independent auditor can certify missing or inconsistent endpoint evidence.**
   - File: `scripts/verify_daily_hkd.py:91` and `scripts/verify_daily_hkd.py:97`.
   - Symptom/source: the auditor reads only reconciliation row 0, uses truncating `zip` for endpoint comparison, and checks actual price dates but not the reconciliation's actual FX dates/ages. Empty/short endpoint tables skip required comparisons; corrupted exported FX dates can remain undetected.
   - Consequence: an in-memory mutation that deletes all `computed.fx_endpoints` rows and changes `reconciliation.fx_end_observed_date` to `1900-01-01` still returns both `all_comparisons_agree=True` and `all_hkd_previews_valid=True` against the actual verified S01 manifest. The CLI could therefore publish an empty endpoint CSV and inconsistent reconciliation dates under a successful independent verification report.
   - Remedy: require the exact expected reconciliation/endpoint cardinality and date keys before comparing values; compare the reconciliation FX observed dates and ages to the independent references. Add separate tamper tests for missing/extra endpoints, unexpected reconciliation rows, and wrong exported FX dates/ages. Keep the independent reference path separate from production selection.

4. **The inherited price-cache boundary also removes unknown dates before C1 can block them.**
   - File: `src/portfolio/data/monthly_cache.py:26` (unchanged code, directly consumed by the new page at `app/views/daily_hkd.py:149`).
   - Symptom/source: the Yahoo parser preserves a null timestamp as a missing date, but the cache adapter's range filter discards it before `aggregate_daily_prices` can apply its `invalid_date` rule. This is the same concrete boundary defect as issue 1, on the price side.
   - Consequence: a complete 41-session December 2024/January 2025 SPY response plus a 42nd null-timestamp row with positive OHLC/adjusted close passes upstream `audit_price` as `success`. `cached_monthly_prices` returns 41 sessions, zero invalid-date diagnostics, and January local return `0.10000000000000009` with `status=valid` and `reason=ok`. C2 consequently receives an apparently valid price input despite unlocatable raw price evidence. This bypasses the C1 quality boundary on which C2 relies.
   - Remedy: reject or preserve unlocatable dates before the price-cache range filter, as on the FX side. Add one focused price-cache regression with a complete schedule plus a null timestamp and confirm that it cannot yield a valid C1/C2 price result. Keep the fix limited to this consumed boundary; no broader C1 redesign is needed.

#### Minor (Nice to Have)

- `app/views/daily_hkd.py:44`: discovery verifies every run before filtering, so a corrupt unrelated snapshot prevents selecting a sound run. This is the already disclosed fail-closed usability limitation. A later discovery improvement can isolate failed runs while visibly reporting them.
- `outputs/acceptance/S04C2/full_tests.txt:9`: the two existing XHKG/NumPy timedelta deprecation warnings remain. Current tests pass; track the upstream maintenance issue separately without suppressing it or changing dependencies in this step.

### Recommendations

Fix the Yahoo raw-date handling on both cache boundaries, preserve FX raw row provenance, and strengthen the independent comparison contract before accepting C2. Run the affected cache/connector/auditor tests and regenerate the real replay evidence after fixes. The observed defects do not require changing the S03 formula, broadening scope to C3, or performing new network requests.

### Assessment

**Overall: Needs fixes.**

**Ready to merge? No.**

**Reasoning:** The normal numerical and UI paths are well covered, but the raw-date and raw-row guarantees have concrete counterexamples, and the independent acceptance script can return success for missing/inconsistent evidence. These are material gaps in the step's explicit validation and auditability requirements.

### Focused review verification

No broad test rerun was performed. A read-only Python probe used in-memory mocks only at the snapshot byte-loading boundary, exercising the real Yahoo parser, upstream audit, C2 cache transformation and C2 connector for the two raw-response cases. Both upstream statuses were `success`; the null-date case was valid after silently dropping the third row, and the reordered case emitted reversed raw ordinals. A separate in-memory wrapper altered only the production result returned to the real legacy auditor; with zero FX endpoint rows and the wrong FX observation date it still reported full agreement. No source, snapshot or acceptance result was mutated by these probes; this report is the only review-authored file.

Additional controller-requested inherited-boundary probe: generated the actual SPY schedule through `sample_daily_prices('SPY', '2025-01', '2025-01')`, encoded its 41 dates as New York timestamps with matching positive OHLC/adjusted-close arrays and volume 1000, then appended timestamp `None`, prices 120.0 and volume 1000. The real `parse_yahoo_chart` returned one missing date and the real `audit_price(..., start='2024-12-01', end='2025-02-01')` returned success. In-memory patches of only `monthly_cache.load_snapshot` and `read_artifact` supplied that status and raw response to the real `cached_monthly_prices(..., confirmed=True, as_of='2025-02-02T00:00:00+00:00')`; the returned valid/10% result and absent diagnostic confirmed issue 4. No source or fixture file was written.

## Re-review after the four fixes

**Current overall verdict: Approved.** This supersedes the initial Needs fixes assessment above; the original findings remain preserved as the review history. No unresolved Critical or Important finding was identified in the repaired implementation. The two previously recorded Minor items remain nonblocking.

### Fix verification

1. **Unknown FX dates — resolved.** `src/portfolio/data/fx_cache.py:25` calls the new `validated_timestamp_rows` before the production parser and range filter. The helper in `src/portfolio/data/providers/yahoo.py:10` checks original timestamps for numeric/nonboolean/finite values, representability, missing dates and duplicate instants. Thus the identified unknown-date cases are rejected before any source row can disappear. The existing Yahoo parser and upstream audit are unchanged.
2. **FX raw row provenance — resolved.** `src/portfolio/data/fx_cache.py:32` maps retained `timestamp_utc` values back to the original one-based array ordinals returned by the helper. Sorting and range filtering no longer redefine source row numbers. The new real-snapshot regression verifies reversed raw order produces source rows `[2, 1]`, propagates them to endpoints, and leaves stored bytes unchanged.
3. **Independent evidence comparison — resolved.** `scripts/verify_daily_hkd.py:91` requires exactly one January reconciliation row and exactly the two unique expected endpoint labels before accessing records. Endpoint comparisons use a keyed lookup; reconciliation FX observed dates, ages and actual quotes are checked against independent raw references. The 16-case tamper regression covers missing/extra/duplicate/wrong-date evidence, wrong FX dates/ages/quotes and missing endpoint ages. The reference date and ratio calculations remain independent of production selection. Existing missing-FX and latest-invalid diagnostic cases still pass.
4. **Unknown cached price dates — resolved.** `src/portfolio/data/monthly_cache.py:22` uses the same helper before parsing and date filtering. The added complete-calendar snapshot regression first verifies the upstream status really is success, then requires the C1 cache adapter to reject the undated extra row and preserve snapshot bytes. This is a bounded fix to the inherited cache boundary consumed by C2.

### Evidence and remaining delivery checks

Reviewed the regenerated 1,276-line diff's fix additions, corresponding current source and new regression cases, `final-fix-report.md`, `final-fix-green.txt`, and regenerated `legacy_replay/independent_verification.json`. The post-fix covering command reports **133 passed, 2 existing warnings in 4.46s**. The real replay still reports both comparison/preview success flags, retains global partial status and historical ineligibility, and independently gives SPY HKD return `0.030586128808627544` and 2800.HK return `0.010869455644421322`.

No further tests were run by this reviewer: the code and focused regression evidence resolve the named doubts without a new uncertainty requiring execution. The controller's final full regression, package reinstall and browser checks remain subsequent delivery gates; the earlier 420-pass full-suite result predates these fixes and is not presented as post-fix full-suite evidence. No source changes were made during re-review.

### Additional controller-requested timestamp robustness check

After the re-review above, the controller requested one further concrete boundary check. With the current source explicitly on `sys.path`, calling `validated_timestamp_rows` with raw timestamp integer `10**400` raises `OverflowError: int too large to convert to float`. `math.isfinite(stamp)` at `src/portfolio/data/providers/yahoo.py:14` executes before the helper's `try` block. This does not accept invalid data or revive any of the four Important findings, but a success-labelled malformed cache could escape the UI's expected exception handling rather than show its normal error/retraction path. The ordinary downloader already rejects such an unparseable response, so this is classified as **Minor robustness**, not an additional Important issue. Move numeric validation inside the guarded block (or normalize this overflow to `ValueError`) and add the large-integer case to the existing focused timestamp test. The overall Approved verdict for the four required fixes stands. No source file was modified by the review.

### Final review closure

**Final verdict: Approved.** All four Important findings and the additional oversized-integer Minor are resolved. Inspection of `src/portfolio/data/providers/yahoo.py:14` confirms that numeric validation now executes inside the `try` whose exception handler normalizes `OverflowError` to `ValueError`. `tests/test_fx_cache.py:64` includes `10**400`; `final-fix-minor-red.txt` records the intended pre-fix failure, and `final-fix-minor-green.txt` records **63 passed, 2 existing warnings in 1.42s** after the fix.

No further test run or source edit was needed for this closure. The unrelated corrupt-cache discovery limitation and upstream calendar deprecation warnings remain the two previously accepted nonblocking Minor items. Final full-suite/runtime/browser/documentation completion belongs to the controller's remaining delivery checks; this approval is the code-review conclusion, not a claim that those subsequent checks have completed.
