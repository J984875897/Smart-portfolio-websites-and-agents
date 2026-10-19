### Spec Compliance

- ✅ Spec compliant for Task 1: fixed catalog, validated plans, one public request per item, immutable publication, exact raw bytes, partial/cancelled handling, offline reads, and shared S01 implementation are present in the diff.
- ⚠️ UI retention of the opened cache after failed refresh is outside this task's diff; controller owns integration verification. `scripts/verify_downloads.py` is the controller's acceptance utility.

### Strengths

- `src/portfolio/data/providers/yahoo.py:77` makes one direct public chart request with redirects disabled and without login, cookie, crumb, key, or retry machinery. `src/portfolio/data/updates.py:16` validates the complete selection before creating a run or fetching.
- `src/portfolio/data/updates.py:44` isolates expected transport failures while allowing local IO failures to propagate. Raw bytes are saved before HTTP/parse/cancellation classification (`updates.py:50`); no exception text enters the manifest.
- `src/portfolio/data/updates.py:76` stages complete runs under root and atomically publishes a distinct timestamp/UUID directory. Existing run directories are untouched. Tests cover both revision preservation and local write failure (`tests/test_updates.py:23`, `tests/test_updates.py:88`).
- `src/portfolio/data/snapshots.py:45` verifies every listed artifact's hash and size, path containment, references, and status constraints before reads; reads contain no network operations. `tests/test_updates.py:113` exercises corruption and symlink/path boundaries.
- `scripts/probe_sources.py:98` imports the extracted parser/audit, and the diff shows their original bodies moved without a parallel implementation. `updates.py:58` filters start-inclusive/end-exclusive dates before the shared audit; partial rows keep missing values and imports require success (`updates.py:67`).

### Issues

#### Critical (Must Fix)

- None.

#### Important (Should Fix)

- None.

#### Minor (Nice to Have)

- `src/portfolio/data/snapshots.py:74`: manifest validation checks that an import implies non-FX success, but does not check the reverse: a non-FX success should have an import. An accidentally edited manifest can therefore discard its import reference and corresponding file entry yet still load as success. Consider validating the reverse relationship, alongside the existing raw/daily evidence requirement. Normal writer output satisfies the relationship (`updates.py:67`), so this does not block the implemented update path.

### Assessment

**Task quality:** Approved.

**Reasoning:** The implementation meets the task's public behavior and failure boundaries, with focused tests covering the consequential paths. The remaining suggestion strengthens detection of semantic manifest corruption rather than correcting the normal update workflow.

**Review checks:** Read the supplied brief/report and diff; the initial tool output truncated the provider/snapshot/update hunks, so only those omitted diff sections were retrieved. No changed source files were separately reread, no broader crawl or Git commands were used, and no already-reported tests were rerun. The reported 58-pass GREEN is implementer evidence, not an independently repeated suite result.
