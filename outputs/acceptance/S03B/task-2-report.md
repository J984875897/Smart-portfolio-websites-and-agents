# S03-B Task 2 evidence

Implemented `app/views/alignment.py`, updated `app/main.py` and the minimal result origin / warning in `app/views/hkd_returns.py`, and added `tests/test_alignment_view.py`. Core files, README, workflow status and parent acceptance records were not edited by this task.

## UI and handoff

Sidebar now has 数据导入, 港币收益查验, 共同窗口查验; default stays 数据导入. Alignment defaults to the previous HKD result, explicit end month 2025-01 and explicit Hong Kong decision `2025-01-31T17:00:00+08:00`. The action is 查验共同窗口. Synthetic mode is labelled 人工测试案例, runs the independent five-asset core sample through its existing real S03-A conversion, and uses separate artificial timing. Default early decision produces one eligible asset; late `2025-02-01T06:00:00+08:00` produces two. Chinese summary precedes monthly statuses and expandable full evidence. Fixed matrix and all three report/coverage/matrix CSV downloads appear only for the current successful fingerprint. Template is separately available before calculation.

S03-A stores result origin with source bundle content/schema/evidence fingerprint and calculation input fingerprint. The alignment page compares the saved-source bundle content before accepting a previous result, even if bundle_version never changed. Previous synthetic HKD results are permitted with an explicit synthetic/short-history label. Missing handoff gives navigation guidance and disables calculation. Mode, upstream reconciliation content, end month, decision, timing mode, file bytes/name and worksheet all contribute to the fingerprint; errors clear stale results. Uploaded timing is the complete unmodified `read_file` frame, preserving authoritative file/sheet/physical row/hash evidence.

Help renders `docs/data/alignment_format.md`, including available_at semantics, endpoint timing, seven-day research threshold, provenance, conservative month maturity, revisions and limitations. Summary states report count is not formal N, missing rows are retained rather than zero-filled, no older months substitute, true 0% can be valid, and S03-C remains unfinished. Native Streamlit components only; no global font CSS.

## Actual RED/GREEN commands

1. Initial `.venv/bin/python -m pytest tests/test_alignment_view.py tests/test_hkd_returns_view.py -q`: collection exit 2 due to test importing sample from alignment rather than the actual alignment_samples module. Corrected test import before feature implementation.
2. Same command RED: exit 1, **4 failed, 7 passed in 2.21s**. All four failures expected: third navigation page absent.
3. After implementation same command: exit 1, **2 failed, 9 passed in 2.95s**. Synthetic mode inherited previous upload selection, causing no timing; fixed mode-switch reset. Provenance assertion incorrectly included missing periods' NaN; restricted the assertion to present timing evidence.
4. Same command: exit 1, **1 failed, 10 passed in 2.92s**. Changed upload test used an uppercase byte sequence absent from fixture; corrected fixture to append a newline so bytes really differ. This checks byte-content invalidation with unchanged logical rows.
5. Same command: exit 0, **11 passed in 3.31s**, with four pandas deprecation warnings from display dtype selection.
6. Added Chinese name/download-content/invalid-decision test before correction; `.venv/bin/python -m pytest tests/test_alignment_view.py -q`: exit 1, **1 failed, 4 passed in 2.49s**. SHORT_HISTORY displayed raw ID rather than Chinese short-history name. Corrected name mapping and explicit object/str dtype selection for display.
7. Final targeted `.venv/bin/python -m pytest tests/test_alignment_view.py tests/test_hkd_returns_view.py -q`: exit 0, **12 passed in 3.64s**, no pytest warnings.

Full-evidence display serializes nested evidence to JSON and mixed object values to strings in a display-only copy, avoiding Arrow conversion failures; downloadable core evidence remains untouched. All calculations call align_monthly rather than reproducing core logic.

## Covered behaviors and scope

AppTest verifies default navigation, no-data guidance/disabled action, independent synthetic isolation, early1/late2 and fixed60, changed decision/end month clearing old downloads, current saved-source content staleness without version change, previous synthetic handoff label, uploaded CSV provenance, changed file bytes, malformed XLSX, Excel worksheet changes, Chinese scenario naming, actual downloadable matrix dates/columns/values, and offset-free decision rejection. Existing seven S03-A view regressions remain passing.

Self-review checked authoritative timing frame handoff, source content binding, current-result-only downloads, no saved bundle mutation, isolated widget keys, evidence retention, Chinese summary first, and explicit limitations. AppTest execution is recorded here; no visual browser check was performed by this task. Parent owns independent review, full-suite verification, actual browser/runtime checks, and final acceptance/workflow documentation. No Git initialization, network or new dependencies.

## Parent inspection correction

Parent identified the synthetic token initially used only a scenario constant. Added a regression that changes the generated synthetic reconciliation without changing widgets. Actual RED `.venv/bin/python -m pytest tests/test_alignment_view.py -q`: exit 1, **1 failed, 5 passed in 3.13s**; old result remained. Fingerprint now binds actual synthetic reconciliation, timing and requested asset contents. Also renamed the monthly retained value column to `原始换算值（小数，阻止行不可用）` so blocked rows cannot be mistaken for usable returns. SHORT_HISTORY Chinese mapping was already corrected and tested. Actual final targeted `.venv/bin/python -m pytest tests/test_alignment_view.py tests/test_hkd_returns_view.py -q`: exit 0, **13 passed in 4.05s**, no pytest warnings.

## Independent review fixes

Review `task-2-review.md` found an all-blocked S03-A reconciliation was still selectable and real-source product names fell back to IDs. Added two AppTest regressions before implementation. Actual RED `.venv/bin/python -m pytest tests/test_alignment_view.py tests/test_hkd_returns_view.py -q`: exit 1, **2 failed, 13 passed in 4.74s**; calculation incorrectly enabled for all-blocked handoff and saved product name displayed SYNTH_HKD.

Now previous HKD handoff requires at least one status=valid row; an all-blocked result clears prior alignment, disables calculation and tells users to fix monthly total-return/adjusted-price confirmation/endpoint FX first. If any valid row exists, the full asset list remains requested, so blocked assets remain in the report. Real saved-source display names come from current bundle.assets.name; independent artificial scenarios keep explicit synthetic Chinese names. Actual GREEN same command: exit 0, **15 passed in 4.56s**, no pytest warnings. No root docs or core changed. Ready for final parent browser checks.

## Actual browser state regression

Parent's real browser check found artificial mode still displayed the timing uploader and yielded 0/5 eligible, despite the original AppTest path passing. Investigated installed Streamlit selectbox/session-state code: a keyed selectbox uses its key as identity, ignoring changes to options; deleting the server-side key does not provide an authoritative replacement for the prior frontend selection. On mode change the browser could therefore restore 上传时间证据. The AppTest path did not model this restoration.

Added a focused regression that models restoring the prior upload value at selectbox registration when application code has left no authoritative session value. Actual RED `.venv/bin/python -m pytest tests/test_alignment_view.py tests/test_hkd_returns_view.py -q`: exit 1, **1 failed, 15 passed in 4.81s**; artificial mode wrongly selected 上传时间证据. Minimal fix assigns the mode-specific default explicitly before widget registration: 人工时间证据 for artificial mode, 上传时间证据 for previous HKD mode. Existing same-mode user selections remain intact. Actual GREEN same command: exit 0, **16 passed in 4.99s**, no pytest warnings. Regression also computes early fixed60/one-asset result and checks switching back restores upload mode. Actual browser confirmation belongs to parent's enhanced count assertions; no browser script edits by this task.
