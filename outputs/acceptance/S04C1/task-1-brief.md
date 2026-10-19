### Task 1: 日历、聚合与只读缓存核心

**Files:** 新建 src/portfolio/data/trading_calendar.py、daily_monthly.py、monthly_cache.py、tests/test_daily_monthly.py；修改 pyproject.toml、requirements.lock.txt。

**Interfaces:** trading_schedule(market,start,end)->DataFrame；aggregate_daily_prices(prices,*,symbol,start_month,end_month,confirmed=False,as_of=None)->DailyMonthlyResult(sessions,monthly,returns,metadata)；cached_monthly_prices(root,run_id,symbol,*,start_month,end_month,confirmed=False,as_of=None)->DailyMonthlyResult。完整字段及行为见设计文档。

- [ ] 写失败检查：测试内局部 import 未交付 API，使缺功能表现为正常测试失败；人工完整样本可使用日历生成日期，已知期末100/110，独立假期与 DST 断言不能从生产日历生成预期。
  ```python
  def test_monthly_ratio():
      from portfolio.data.daily_monthly import aggregate_daily_prices
      result = aggregate_daily_prices(prices, symbol='SPY', start_month='2025-01', end_month='2025-01', confirmed=True, as_of='2025-02-02T00:00:00Z')
      assert result.returns.iloc[0].local_return == pytest.approx(.1)
  ```
- [ ] 运行 `.venv/bin/python -m pytest tests/test_daily_monthly.py -q`，保存 RED 与失败原因。覆盖设计的失败案例、官方日期、缓存损坏/身份/partial、输入不修改及不联网。
- [ ] 实现三份核心；必要时将纯验证辅助函数放同职责模块，避免全量重构。用 DataBundle 临时承载合法月末价格，并调用 build_local_returns，不重新写收益公式。返回表包含所有阻止月份及 NaN；不让报表标签代替可用性认证。
- [ ] 固定依赖新增 exchange_calendars==4.13.2、korean_lunar_calendar==0.4.0、pyluach==2.3.0、toolz==1.2.0、tzdata==2026.5；不改变旧依赖版本。
- [ ] 同一命令 GREEN，再运行 `.venv/bin/python -m pytest tests/test_returns.py tests/test_updates.py tests/test_daily_monthly.py -q`；自审、报告 outputs/acceptance/S04C1/task-1-report.md，交给审查者验收。


Read the full design at docs/superpowers/specs/2026-10-16-s04c1-daily-monthly-design.md. This is the binding detailed contract. No Git repository; do not initialize Git or commit. Dependencies already installed; edit declarations/lock only. Use apply_patch for edits. For tests, use local imports to capture missing-feature failures normally. Save RED/GREEN logs in this acceptance folder. Report full TDD commands/results and concerns in task-1-report.md. Read TDD skill and its testing-anti-patterns reference before implementation. Work only in Task1 owned files; do not edit UI, docs or other scripts.

