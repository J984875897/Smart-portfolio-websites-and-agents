# S04-A final fixes report

DONE: all three verified Minor findings addressed in one focused offline fix wave.

## Implementation

- Snapshot validation now requires an import artifact for every successful non-FX product, retaining the HKD=X exception and existing raw/daily, reference, size and hash checks.
- New manifests record `provider_endpoint_version: v8`, `adapter_version: yahoo-chart-v1`, and exact installed-runtime Python, yfinance, curl_cffi and pandas versions using platform/importlib metadata. Old schema1 manifests without these optional metadata fields still load. `created_utc` retains its run-start meaning; existing snapshots and raw caches were not rewritten.
- A separate Chinese diagnostic expander previews and exports partial daily files, retaining NaNs and exact stored CSV bytes. Both opened mixed caches and all-partial result records are supported. All-partial records retain prior active cache. Result and active diagnostics use separate widget prefixes, with duplicate rendering suppressed for the same run. Snapshot verification, manifest equality and artifact verification precede diagnostic display/export. Partial symbols remain outside the success selector and have no import handoff.

## RED evidence

Exact command:

```sh
.venv/bin/python -m pytest tests/test_updates.py tests/test_downloads_view.py -q > outputs/acceptance/S04A/final-fixes-red.txt 2>&1
```

Exit 1: **3 failed, 31 passed in 1.56s**. Failures were the expected missing import-evidence rejection, missing provider metadata, and missing diagnostic download. Tests were written and this result inspected before implementation.

## GREEN evidence

Exact command:

```sh
.venv/bin/python -m pytest tests/test_updates.py tests/test_source_probe.py tests/test_downloads_view.py tests/test_data_center.py -q > outputs/acceptance/S04A/final-fixes-green.txt 2>&1
```

Exit 0: **78 passed in 5.72s**. No fullsuite was run.

## Files changed

- `src/portfolio/data/snapshots.py`
- `src/portfolio/data/updates.py`
- `app/views/downloads.py`
- `tests/test_updates.py`
- `tests/test_downloads_view.py`
- Acceptance evidence/report: `final-fixes-red.txt`, `final-fixes-green.txt`, `final-fixes-report.md` in this directory.

## Self-review and concerns

The regression constructs a valid writer-produced success manifest before deleting both import reference and corresponding file entry. Runtime provenance assertions compare exact installed distribution versions; UI export assertions confirm the manifest carries those fields. Legacy optional-field omission is exercised. Diagnostic coverage includes mixed and all-partial runs, exact byte capture, NaN preview, success-only selection, prior-active preservation, duplicate suppression, changed-manifest rejection and corrupt-file rejection. Existing handoff/reset/failure/FX guards remain covered by the focused tests. Existing Chinese UI copy and preview columns were preserved; only diagnostic copy was added. No network, dependency installation, Git operation, monthly computation or unrelated refactor was performed.

No implementation concerns identified. Tests resolve source via project pytest pythonpath; controller must reinstall the standard-installed core before final fresh fullsuite, as specified in the brief.
