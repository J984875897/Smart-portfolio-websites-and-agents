# S03A Important review fix: authoritative FX file provenance

Addressed the Important finding in `validate_fx`: submitted `source_file`, `source_sheet`, `source_row`, and `source_hash` columns previously overrode actual `read_file` metadata through `setdefault`.

Frames carrying `raw_bytes` now use file attributes, physical source rows, and the SHA-256 of actual bytes for all four evidence fields. This reaches validated scalar evidence, duplicate evidence, issue rows, and reconciliation. Truly in-memory frames continue to preserve caller-supplied manual evidence. Caller frames are not mutated. Code scope: `src/portfolio/data/fx.py` and `tests/test_fx.py`; no dependencies or commits.

## Actual red verification

Command: `.venv/bin/python -m pytest tests/test_fx.py -k 'file_metadata_overrides or in_memory_manual' -q`

Before production changes, the CSV and XLSX regressions failed because `old.csv`, `old-sheet`, `999`, and `old-hash` survived in evidence. Actual output:

```text
FAILED tests/test_fx.py::test_file_metadata_overrides_submitted_provenance[csv]
FAILED tests/test_fx.py::test_file_metadata_overrides_submitted_provenance[xlsx]
2 failed, 1 passed, 13 deselected in 0.43s
```

CSV regression uses a real temporary file with blank lines and verifies physical rows 3 and 5. XLSX regression verifies worksheet `Quotes`, rows 2 and 3, and SHA-256 of the actual workbook bytes. Both verify full source dictionaries, reconciliation evidence, and unchanged inputs. A separate in-memory regression preserves manual provenance.

## Actual green verification

Command: `.venv/bin/python -m pytest tests/test_returns.py tests/test_fx.py -q`

```text
.................................                                        [100%]
33 passed in 0.39s
```

This fixes only the reviewed provenance defect; S03B/C remain outside this delivery.
