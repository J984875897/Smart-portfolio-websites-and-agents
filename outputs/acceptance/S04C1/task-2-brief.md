### Task 2: 三步操作页面与状态检查

**Files:** 新建 app/views/daily_monthly.py、tests/test_daily_monthly_view.py；修改 app/main.py；需要的人工样本函数可放 src/portfolio/data/daily_monthly_samples.py。

**Interfaces:** 使用 Task1 函数；downloads_root 遵守 PORTFOLIO_DOWNLOADS_ROOT，所有会话键 dm_。页面标题／侧栏「日线月度查验」。s['dm_result'] 只保留当前有效 DailyMonthlyResult，s['dm_token'] 输入指纹，缓存 manifest 变化失败关闭。

- [ ] 写 AppTest 失败检查，默认无结果/无网络；完整人工100→110；未确认阻止；改参数撤下结果；缺最后和中间报价；缓存只读及损坏后无结果导出；跨页不改 bundle。以真实核心为主，仅拦截网络调用，不模拟整个核心。
  ```python
  at.radio(key='workspace').set_value('日线月度查验').run()
  at.checkbox(key='dm_confirm').check().run()
  at.button(key='dm_compute').click().run()
  assert at.session_state['dm_result'].returns.iloc[0].local_return == pytest.approx(.1)
  ```
- [ ] 运行 `.venv/bin/python -m pytest tests/test_daily_monthly_view.py -q` 保存 RED。
- [ ] 按页面「1 选择来源 → 2 产品与月份 → 3 查验结果」实现。来源 radio dm_mode=['人工案例','已下载缓存']；案例 dm_case=['完整报价','缺最后交易日','缺月中交易日','重复日期']；dm_symbol 六个价格代码（默认SPY），缓存仅列可诊断的 success/partial 且有 raw_file 项；dm_run 可选已有 schema1 版本，损坏记录显示中文错误不静默消失。dm_start_month/dm_end_month 默认2025-01；dm_confirm 默认False；dm_compute 文案「查验日线并计算月收益」。人工价格前月100、本月110，案例固定Dec2024/Jan2025，修改月份应生成该目标月份的同样人工规则，保持人工标签；未来月受成熟规则阻止。
- [ ] 先中文指标（目标月数／可预览收益月数）、月末及收益百分比表、逐月中文阻止原因，再 expander「逐日明细与来源证据」含三张完整表、metadata JSON和CSV下载。USD 保持原币明确显示；每次重新渲染重新验证真实缓存和manifest，缓存指纹包括root及manifest与输入。参数变化后无旧结果和下载。提示看一月收益须下载完整2024-12-01至2025-02-01；本页不下载、不自动提交。保持原 Material 字体修复，不加全局 CSS。
- [ ] GREEN `.venv/bin/python -m pytest tests/test_daily_monthly_view.py tests/test_hkd_returns_view.py tests/test_downloads_view.py -q`；报告 outputs/acceptance/S04C1/task-2-report.md 并审查。


Binding full design: docs/superpowers/specs/2026-10-16-s04c1-daily-monthly-design.md. Core Task1 approved; API actual files trading_calendar.py/daily_monthly.py/monthly_cache.py. DailyMonthlyResult(sessions,monthly,returns,metadata), monthly.date is naturalmonthend, expected_end_date literal market last session; returns date/local_return/status/reason, reason codes from monthly can combine semicolon and previous_month: prefix. Source partial reason source_not_success. metadata historical_eligible=False available_at='', manifest for caches. This is current-vintage original-currency preview only. source_status global partial blocks all returns. Keep six existing pages working. User had trouble understanding prior pages, so clear numbered three steps, one primary compute action, short result explanation; dense evidence in expander. No extra dependencies, globalCSS, network, auto-save or scope expansion. No Git; use apply_patch. Read TDD skill + anti-patterns and follow RED/GREEN; save logs outputs/acceptance/S04C1/task-2-red.log etc and full report task-2-report.md. Only modify Task2 owned files. Parent is independently writing scripts/verify_daily_monthly.py and tests/test_daily_monthly_verification.py; don't edit those. No own agents.

