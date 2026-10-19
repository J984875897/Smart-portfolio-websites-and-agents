### Spec Compliance

- ❌ Issues found: TLS failures are collapsed into generic `transport_error`, contrary to the design's separate fixed TLS reason requirement (`src/portfolio/data/reference_updates.py:21,61-62`; `src/portfolio/data/snapshots.py:106`; design “版本与失败”).
- ✅ The fixed catalog, month-start pre-I/O validation, bounded in-memory French archives, exact model columns, official HKMA parameters and monotonic pagination, retained raw responses, cooperative cancellation, and schema 2 artifact verification implement the task's principal contracts (`src/portfolio/data/reference_updates.py:23-110`; `src/portfolio/data/providers/french.py:11-59`; `src/portfolio/data/snapshots.py:96-146`).
- ⚠️ UI initiation, live source behavior and full-suite compatibility are outside this task's diff. Controller should complete the later acceptance stages; the reported 95-test run was not repeated.

### Strengths

- `src/portfolio/data/reference_updates.py:64-69,72-91`: Raw evidence is written before cancellation/status/parse decisions; invalid later HKMA pages cannot turn prior observations into success, and failed French model checks cannot publish unfiltered history.
- `src/portfolio/data/reference_updates.py:73-77,95-104`: Pagination uses actual returned rows and short-page exhaustion; monthly coverage stays explicitly limited to observation months.
- `src/portfolio/data/snapshots.py:104-146`: Identity, listed/referenced artifacts, hashes/sizes, success evidence, coverage fields and unexpected on-disk files receive explicit checks.
- `tests/test_reference_updates.py:26-176`: Tests exercise real archives, parsers and published files through an injected transport boundary, including old-version retention and corrupt/symlink artifacts.

### Issues

#### Critical (Must Fix)

- None.

#### Important (Should Fix)

- `src/portfolio/data/reference_updates.py:21,61-62`; `src/portfolio/data/snapshots.py:106`: The inherited `_transport_reason` only distinguishes timeout from generic transport failure. Injecting curl `RequestException(code=60)` produces `transport_error`; official HKMA TLS failures therefore cannot be identified using the manifest's safe reason codes despite the explicit design requirement. Add a reference-specific fixed TLS reason mapping (including relevant curl TLS/certificate error codes), permit it in schema 2, and add a focused injected-error test without persisting exception text.

#### Minor (Nice to Have)

- `src/portfolio/data/snapshots.py:101,133`: `datetime.fromisoformat` accepts timezone-free values for `created_utc` and `retrieved_utc`, so schema 2 does not fully enforce its UTC timestamp contract. A focused manifest mutation confirmed that `2025-01-01T00:00:00` is accepted. Require an explicit UTC offset for these fields.
- `src/portfolio/data/reference_updates.py:23-117`; `src/portfolio/data/snapshots.py:96-146`: Many validation and state transitions share dense single lines. Expand the conditional blocks, especially pagination/status transitions and item validation, to keep future correctness review manageable.

### Assessment

**Task quality:** Needs fixes.

**Reasoning:** The central data and evidence contracts are implemented carefully, with substantive offline boundary tests. The explicitly requested TLS classification remains missing and should be fixed before task acceptance.

**Focused checks:** Named risk: shared transport helper may erase required reference-specific TLS classification. Inspected only `src/portfolio/data/updates.py:32-41` outside the diff; injected curl certificate error 60 confirmed `transport_error`. Named risk: timestamp validation may accept non-UTC fields; mutated one temporary manifest and confirmed naive timestamp acceptance. Executed one successful offline probe using `PYTHONPATH=src .venv/bin/python` after importing yfinance before curl. Two setup-only probe attempts failed first on the known curl dynamic-library initialization order, then on missing `PYTHONPATH`; no network calls or suite runs occurred. No changed source was reread except the existing snapshot loader envelope to check how schema-2 validation errors are normalized. All probe artifacts were temporary.

### Reassessment after review fixes

- ✅ **Spec compliance: Approved.** `src/portfolio/data/reference_updates.py:50-62` now maps curl TLS/certificate codes and `SSLError` to fixed `tls_error`, preserves timeout classification, and exposes no exception text. `src/portfolio/data/snapshots.py:106` permits the new reason. The prior blocking finding is resolved.
- ✅ **Quality: Approved.** `src/portfolio/data/snapshots.py:101,133,152-158` now validates explicit UTC offsets on both timestamp fields. `tests/test_reference_updates.py:180-210` covers TLS 35/60, generic 7, timeout 28, message non-disclosure, both timestamp locations, code-free SSLError and legacy adapter reading. `src/portfolio/data/reference_updates.py:132` identifies future writes as reference-v2 while the loader preserves v1 compatibility.
- **Remaining Minor:** Dense validation and pagination statements remain in `src/portfolio/data/reference_updates.py:85-123` and `src/portfolio/data/snapshots.py:103-138`. The touched error/cancellation blocks are clearer; remaining formatting is nonblocking.
- **Checks:** Focused static review of the updated diff and report only. Report records RED 6 failed/37 passed and GREEN 104 passed; no suite rerun, live request, or artifact mutation was performed. Only this review report was appended.
- ⚠️ Live behavior, UI initiation and full-suite acceptance remain controller responsibilities as previously scoped.
