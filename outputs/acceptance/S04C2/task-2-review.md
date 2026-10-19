### Spec Compliance

- ✅ Spec compliant for the task-scoped implementation: the appended sidebar branch preserves the seven previous routes (`app/main.py:15`); the three steps, explicit compute, defaults, HKD bypass and source choices appear at `app/views/daily_hkd.py:61–163`. Synthetic helpers remain outside app and reuse C1 month validation (`src/portfolio/data/daily_hkd_samples.py:7–39`).
- ✅ Invalidation includes source modes, cases, symbol/months, confirmations, policy, resolved roots, manifests and upload bytes/name/sheet (`app/views/daily_hkd.py:142–146`). Cache reads run on every render, errors clear results and disable computation (`app/views/daily_hkd.py:106–115,147–163`). Downloads are reachable only after a result exists (`app/views/daily_hkd.py:165–195`).
- ✅ The page delegates conversion to the core, labels SYNTH/official/unofficial/imported combinations, exposes Chinese reconciliation and actual endpoint evidence, and exports six raw tables plus metadata (`app/views/daily_hkd.py:100–101,140,159–195`).
- ⚠️ Cannot verify from diff: native browser upload/download behavior, narrow/wide screenshots, and full regression remain controller acceptance items. Existing routes are preserved by the diff; their full interactive behavior is covered by the controller’s broader regression gate.

### Strengths

- `tests/test_daily_hkd_view.py:30–210`: behavioral AppTests exercise computed values, both confirmations, HKD, diagnostic failures, root/manifest/upload changes, actual CSV/XLSX parsing, cache byte corruption and read-only state. Upload transport substitution is explicitly disclosed rather than presented as a native browser test.
- `app/views/daily_hkd.py:120–131,149–163`: uploaded provenance is retained through the existing parser, cached prices are revalidated before use, and computation retracts the previous result before attempting new work.
- `src/portfolio/data/daily_hkd_samples.py:7–39`: small independent offline examples clearly mark synthetic provenance and use actual exchange sessions.

### Issues

#### Critical (Must Fix)

- None.

#### Important (Should Fix)

- None.

#### Minor (Nice to Have)

- `outputs/acceptance/S04C2/task-2-green.log:3–6`: two upstream XHKG NumPy timedelta deprecation warnings remain. They are documented, pre-existing calendar dependency noise rather than a new UI defect; track the dependency fix separately, without suppressing warnings in this task.
- `app/views/daily_hkd.py:44–47`: discovery verifies every snapshot before filtering candidates. A damaged unrelated run therefore prevents selecting an otherwise intact cache. This fails closed and is disclosed in the report, so it is not a blocking correctness issue; consider isolating unusable runs with an explicit diagnostic in a later cache-discovery improvement.

### Assessment

**Task quality:** Approved

**Reasoning:** The changed page implements the requested read-only lifecycle and evidence presentation without duplicating conversion logic. No blocking discrepancy was found; native/browser and full-regression checks remain outside this task review.

**Checks:** Read the scoped diff and binding brief/design constraints. Named outside-diff risk: whether UI cache calls actually recheck bytes and propagate partial status; inspected `src/portfolio/data/monthly_cache.py:9–33`, `src/portfolio/data/fx_cache.py:11–66`, and `src/portfolio/data/snapshots.py:44–81,140` (verified snapshot entry path) and confirmed raw reparsing/hash verification and source status propagation. Named outside-diff risk: upload errors/provenance and reason-code compatibility; inspected the importer exception/provenance contract and core endpoint/reconciliation codes in `src/portfolio/data/importer.py:15–50` and `src/portfolio/data/daily_hkd.py:19–99`. Read the existing GREEN log: 34 passed, two known upstream warnings. No test rerun was needed.
