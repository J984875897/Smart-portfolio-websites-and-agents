### Task 2: Inspectable Streamlit page and UI verification

**Files:** Create `app/views/risk_free.py`, `tests/test_risk_free_view.py`; modify `app/main.py`. Minimal scope corrections to warning text in `app/views/hkd_returns.py` and `app/views/alignment.py` so they direct users to separate interest-rate checks without implying portfolio/retest completed. Do not change upstream calculations.

**Interfaces:** Consume Task1 APIs verbatim. `render()` exposed for main.py. Sidebar option exactly `港币利率查验`; default remains existing data page. Keys `rf_mode` radio (`人工测试案例`,`上传报价文件`), `rf_case` selectbox (Task1 case names), `rf_end` text default2024-03, `rf_months` integer number_input default3 range1–600, `rf_decision` text default2024-03-31T16:00:00+08:00, `rf_upload`, `rf_sheet`, `rf_compute` button label `查验港币利率代理`, `rf_result` storedresult orNone. Decision UI explicitly requires +08:00 as existing pages do. End/months are editable; sample only covers3 months so longer windows visibly unavailable. Summary includes `可用月份 3 / 3` or `可用月份 2 / 3` and series status. Render rf_hkd as percent in Chinese summary; original decimal stays in evidence/download.

- [ ] Write AppTest before implementation. Exercise default page still data import, navigation, artificial complete exact series, 4failedcases, missing windows, decision immaturity, result and downloads removed when any input changes, invalid decision/format, no upload disables compute, CSV file parsing, XLSX nonfirstsheet, malformed upload no stale result, sample isolation from bundle. Uploads can be injected by monkeypatching Streamlit file_uploader as existing test_alignment_view does; do not claim native upload proven by this test.
```python
at.radio(key='workspace').set_value('港币利率查验').run()
at.button(key='rf_compute').click().run()
assert at.session_state['rf_result'].series.tolist() == pytest.approx([.0031,.0029,.0031])
at.selectbox(key='rf_case').set_value('缺中间报价').run()
assert at.session_state['rf_result'] is None
```
- [ ] Save RED missing-feature output, implement view and navigation using native widgets/current styles. Keep UI formula-free. Track fingerprint from all relevant inputs (mode,case,params,file bytes/name,sheet), clear result before attempting parsing/computation; no silent replay of old results. Catch input ValueError and supported file exceptions, show errors. Template/sample download is separate from two result downloads with labels `下载利率查验报告 CSV` and `下载港币代理收益 CSV`; result downloads exist only for current completed computation. Provide full report as expandable evidence; synthetic/method risks prominent.
- [ ] Run `.venv/bin/python -m pytest tests/test_risk_free_view.py -q`, then existing view tests. Update minimal upstream warning text to say monthly conversion/time checks alone are insufficient and separate proxy is available; no claim of full source certification or Sharpe. Record self-review, RED/GREEN commands/output in task-2-report.md. Independent review required before marking complete.

## Final verification and user handoff (controller)

- [ ] Run full pytest and verify_risk_free.py, reinstall package without network/dependencies for local app imports.
- [ ] Inspect real browser complete/failed sample and changed-input clearing; widths1440/720 no page overflow or icon overlap. Save screenshots and browser checks. If real browser unavailable, explicitly report that limitation rather than substitute AppTest claim.
- [ ] Generate final code diff vs baseline snapshot for independent final reviewer. Resolve all important findings with covering tests and re-review.
- [ ] Update root README, S03 workflow checkboxes/status and S03C acceptance README/progress/checks. Distinguish month-only S03 acceptance from remaining real data limitations. Next step S04 only after user instruction.
