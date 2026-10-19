### Spec Compliance

- ✅ Spec compliant for the core/cache scope: row diagnostics and conservative monthly endpoints (`src/portfolio/data/daily_hkd.py:19`), strict confirmation/partial-source blocking with preserved C1 status (`src/portfolio/data/daily_hkd.py:83`), S03 formula delegation (`src/portfolio/data/daily_hkd.py:68`), and raw snapshot reparsing/identity checks (`src/portfolio/data/fx_cache.py:11`).
- ⚠️ Price snapshot manifest preservation cannot be established from this diff: `src/portfolio/data/daily_hkd.py:97` copies the existing C1 metadata, whose producer currently includes a price hash/source name but no manifest (`src/portfolio/data/daily_monthly.py:44`). The controller should ensure UI/export provenance retains the selected price snapshot manifest/run identity separately. FX manifest preservation is explicit (`src/portfolio/data/fx_cache.py:60`).
- ⚠️ UI invalidation, seven-page compatibility, independent raw-JSON acceptance, and final application regression are outside this task's diff, as intended by the task scope.

### Strengths

- `src/portfolio/data/daily_hkd.py:46`: duplicate/latest-invalid/stale observations block endpoints without falling back; observation diagnostics remain separate from connection eligibility.
- `src/portfolio/data/daily_hkd.py:74`: reconciliation joins every original target row and retains original blocked reasons; HKD conversion remains independent of irrelevant FX failures (`src/portfolio/data/daily_hkd.py:61`).
- `src/portfolio/data/fx_cache.py:38`: ordered page offsets, HTTP status, raw hashes, intervals, lengths and completion are checked before exposing HKMA observations; ordered per-page hashes remain available (`src/portfolio/data/fx_cache.py:49`).
- `tests/test_daily_hkd.py:17` and `tests/test_fx_cache.py:22`: independent numerical assertions, blocking cases and immutable snapshot-byte checks exercise actual behavior.

### Issues

#### Critical (Must Fix)

- None found.

#### Important (Should Fix)

- None found in this task's core/cache changes.

#### Minor (Nice to Have)

- `outputs/acceptance/S04C2/task-1-green.log:8`: two upstream exchange_calendars/NumPy deprecation warnings remain in the reported regression output. These originate in unchanged dependency code, are acknowledged in the implementation report, and do not invalidate the observed 79 passing tests. Track separately for dependency maintenance; avoid broad suppression.

### Assessment

**Task quality:** Approved.

**Reasoning:** The implementation preserves conservative endpoint semantics and delegates financial arithmetic to the existing reconciliation module. Focused tests cover the requested behavioral edge cases; no blocking defect was identified.

- Check performed: read the supplied complete diff once and compared it with the task brief/design and implementer report.
- Concrete external-code risk checks: empty/all-blocked temporary observations and total-return semantics were checked in `src/portfolio/data/returns.py:39` and `src/portfolio/data/fx.py:81`; these functions support the constructed bundle without requiring observation columns when empty.
- Concrete external-code risk checks: page-order validation and full snapshot verification were checked in `src/portfolio/data/providers/hkma.py:39` and `src/portfolio/data/snapshots.py:51`; the cache reader relies on real strict parsing and artifact hashes.
- Concrete external-code risk check: price-side metadata/manifest availability was checked at `src/portfolio/data/daily_monthly.py:44`, resulting in the scoped provenance caveat above.
- No tests rerun: the supplied GREEN log records 79 passed and two known upstream warnings; code inspection raised no unresolved numerical or runtime doubt requiring a focused execution.
