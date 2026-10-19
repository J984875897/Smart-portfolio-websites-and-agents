# Task 1 implementation and self-review

Implemented the seven-entry Yahoo catalog, minimal frozen `RawResponse`, direct public chart transport, pure shared parser/audit, validated request plans, immutable run snapshots, full hash/size verification, offline artifact reads and per-item update history. Existing S01 script imports the extracted functions; both function ASTs were compared with `/private/tmp/portfolio-s04a-before` and are unchanged. Direct script execution adds the repository src directory so its existing CLI still works.

Transport makes one `curl_cffi.requests.get` per selected symbol, timeout 1–30 seconds (default 15), daily observations, all corporate-action categories, UTC start-inclusive/end-exclusive epochs, redirects disabled, and no automatic retry/history/authentication endpoint. `yfinance` is imported solely for required local dynamic-library initialization. Tests intercept the public request and verify exact epochs 1735689600 and 1738368000 for 2025-01-01 to 2025-02-01. No online request was made by this task.

Run IDs combine microsecond UTC timestamp and 32 UUID hex digits. Staging uses a temporary directory inside root; completion atomically renames into runs. Old versions are never rewritten. All actual HTTP bodies, including 429 and malformed bytes, are preserved exactly and hashed. Transport exceptions carry only stable reason codes; exception text is never persisted. Local write errors propagate. Cancellation checks before each item and after response preserve a returned raw body without publishing daily/import files for the cancelled item.

Daily missing values remain missing; partial and unavailable items never get import CSVs. Successful product imports contain ticker/name/tool_type/asset_class/exchange/currency/share_class/frequency/date/value; frequency=daily and value=adj_close. HKD=X has no import CSV. Catalog uses stock/ETF/gold_trust, equity/bond/commodity, and S01 names. Success still means only shared S01 source-field checks, with no calendar/candidate/available-at guarantee.

Offline reads verify all listed files before returning any artifact, including SHA-256, byte size, references, status/import relationships, unique paths, run format, and path containment. Both artifact symlinks and symlinked run directories are rejected. Incomplete staging directories are not listed. Corrupt histories raise rather than silently omit failures. A self-review identified the symlinked runs-directory case; a reproducing RED test was saved and the guard added to writes and reads.

## Verification evidence

- `task-1-red.txt`: initial focused test collection fails because the newly required provider module does not exist.
- `task-1-security-red.txt`: reproduced missing runs-directory symlink protection (1 failed), before adding the guard.
- `task-1-green.txt`: `.venv/bin/python -m pytest tests/test_updates.py tests/test_source_probe.py -q` — **58 passed in 1.19s**.
- Coverage includes immutable revisions, raw equality, single request, parser/actions, bad format, identity, 429, timeout, partial missing prices, mixed outcomes/FX, both cancellation boundaries, invalid parameters with zero requests, network-free reads, corrupt hash, traversal, symlink escape, unlisted artifacts, local IO failure preserving old versions, transport boundary, and S01 regression.

No unresolved implementation concern within Task 1. Full-suite, online, UI, and real-browser acceptance remain controller-owned; no Git initialization, commit, bundle write, UI edit, monthly return calculation, or candidate eligibility work was performed.
