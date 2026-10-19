# S04-A final implementation review

## Strengths

- `src/portfolio/data/updates.py:43` preserves received raw bytes before classification, isolates expected transport failures, propagates local IO errors, and publishes complete runs atomically. Prior run directories are untouched.
- `src/portfolio/data/snapshots.py:45` checks all listed artifact hashes and sizes, references and path boundaries before offline use. `app/views/downloads.py:152` additionally checks the opened identity against disk before exports.
- `app/views/downloads.py:101` confines transport to explicit start; plan, result and active-cache state remain separate. Failed updates/opens retain the old cache. `app/views/downloads.py:38` supplies exact traced CSV bytes to S02, resets mapping/defaults and rotates the uploader without saving the bundle.
- Shared S01 parser/audit extraction preserves existing financial rules. Success remains a source-field check; seven fixed samples, FX direction and the absence of calendar/available-at certification are explicit.

## Issues

### Critical

None found.

### Important

None found within the approved S04-A implementation scope.

### Minor

1. **Successful product import reference is not required on read.** `src/portfolio/data/snapshots.py:75`: a manifest whose non-FX success import reference and corresponding file entry were both removed can still validate. The writer always supplies the import, and the UI safely withholds handoff when absent, so this is semantic-corruption hardening rather than a normal-path failure. Require a non-null import for non-FX success in a future schema-validation improvement.
2. **Runtime provenance is acceptance-level, not per snapshot.** `src/portfolio/data/updates.py:79`: the manifest records provider name and schema version but no client/parser implementation version, narrower than the design's provider/version wording. `runtime_versions.json` documents this acceptance environment but will not follow future exported snapshots. Record runtime/adapter versions in future manifests; existing raw hashes remain valid evidence. `created_utc` is run-start time, not individual response completion or historical available_at.
3. **Partial daily files lack page-level inspection/export.** `app/views/downloads.py:127` and `app/views/downloads.py:157`: partial artifacts remain on disk and their status is visible, but only successful items can be selected for daily display/export. This follows the detailed Task 2 success-only selector, while the design's partial inspection/export wording is broader. Document this limitation; a future separate inspection action can expose verified partial CSVs without making them usable caches or enabling S02 handoff.

## Evidence and scope

Reviewed the design, implementation plan, supplied final diff against the non-Git baseline, current provider/update/snapshot/view code, S02 source-reset contract, task reports and independent task reviews. Inspected recorded full-suite result (**257 passed**) and UI-copy check (**4 passed**); suites were not rerun. Browser evidence records 1440/720 widths, mounted native file upload replaced by traced SPY input, 20 rows, S02 quality check without save, historical mixed-run opening and no new update run. Controller owns the final browser recheck after label polish and final documentation updates.

Real evidence is **two distinct runs**: initial SPY transport failure with 2800.HK 19 rows and HKD=X 22 rows successful, followed by an explicitly requested SPY-only recovery with 20 rows. Both runs have offline replay evidence and raw-to-daily value/hash checks. This is not an all-three-success batch. Runtime package versions are recorded separately. No new network requests or source mutations were made by this review; only this requested report was written.

French/HKMA integration, whole-market discovery, daily trading-calendar certification, daily-to-monthly aggregation and historical availability evidence are outside this delivery. S04 overall is not accepted by this review.

## Assessment

**Ready to integrate: Yes, with the three non-blocking limitations recorded.** The implementation meets the core S04-A download, immutable cache, failure-retention and explicit S02 handoff contract; no unhandled Critical/Important finding was identified. Final acceptance remains contingent on the controller's already-planned final documentation and browser recheck.

## Focused re-review after final fix wave

**Verdict: Approved; all three Minor findings above are resolved for new writer-produced snapshots.** No new Critical/Important or Minor issue identified in this focused review.

- `src/portfolio/data/snapshots.py:76` now rejects successful non-FX items without import evidence; the FX exception and prior full artifact verification remain intact. The regression removes both the reference and file entry, exercising the original hole.
- `src/portfolio/data/updates.py:81` now records endpoint v8, adapter yahoo-chart-v1 and exact Python/yfinance/curl_cffi/pandas versions through local runtime metadata. Reader compatibility with old schema1 manifests is preserved because these additions are optional on read; omission is explicitly covered. Existing snapshots remain unchanged, so their historical provenance limitation remains accurately documented. Run-start timestamp semantics are unchanged.
- `app/views/downloads.py:66` adds separate partial diagnostic preview/export, first verifying the complete snapshot, manifest equality and stored artifact bytes. NaNs and original CSV bytes are retained. Result and active diagnostics have separate keys, duplicates are suppressed, all-partial records preserve the prior active cache, and partial items remain excluded from usable-cache selection and import handoff. New tests exercise those behaviors plus changed-manifest and corrupt-file rejection.

Read the fix brief/report, changed functions and new tests. The reported focused evidence is 3 expected failures before implementation and 78 passing tests afterward; no suite was rerun in this review. Controller's fresh installed-core full regression, final browser checks and documentation remain the final acceptance steps. The earlier review and its evidence are retained above as the pre-fix assessment.
