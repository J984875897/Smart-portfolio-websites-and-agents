# S04-C1 日线月度查验 Implementation Plan

> **For agentic workers:** 使用 subagent-driven-development，逐任务实施、查验与审查；本目录无 Git，使用文件备份 diff，不初始化 Git 或提交。

**Goal:** 用户可在同一页面查看日线完整性、真实月末日期及月度原币收益。

**Architecture:** 日历生成、价格查验与只读缓存适配分开；聚合复用 S03 build_local_returns；Streamlit 只管理输入和结果展示。

**Tech Stack:** Python 3.14、pandas、exchange_calendars 4.13.2、现有 Streamlit／pytest。

## Global Constraints

- 固定六个现有价格样本 AAPL、0700.HK、SPY、2800.HK、AGG、GLD，不接 HKD=X 价格聚合。
- 日历函数范围 2014-01-01 ≤ start < end ≤ 2027-01-01，[start,end)，严格 YYYY-MM-DD。
- 月份严格 YYYY-MM，2015-01 至 2026-12，起止均包含；窗口包含起月之前完整一个月。
- 月度成熟采用该市场下一自然月第一日 00:00 已到的保守规则，等于允许。
- 缺失、重复、非交易日、无效价格不补齐；本月及前月都合格且 confirmed=True 才输出收益。
- available_at=''、historical_eligible=False；日历 close 不表示价格观察或发布时间。
- 只读且不联网，不覆盖快照，不写 DataBundle，不进入 S05；partial 全部收益阻止。
- 换参数、根目录、来源内容或 manifest、确认、案例均撤下旧结果和导出。

### Task 1: 日历、聚合与只读缓存核心

**Files:** 新建 src/portfolio/data/trading_calendar.py、daily_monthly.py、monthly_cache.py、tests/test_daily_monthly.py；修改 pyproject.toml、requirements.lock.txt。

**Interfaces:** trading_schedule(market,start,end)->DataFrame；aggregate_daily_prices(prices,*,symbol,start_month,end_month,confirmed=False,as_of=None)->DailyMonthlyResult(sessions,monthly,returns,metadata)；cached_monthly_prices(root,run_id,symbol,*,start_month,end_month,confirmed=False,as_of=None)->DailyMonthlyResult。完整字段及行为见设计文档。

- [x] 写失败检查：测试内局部 import 未交付 API，使缺功能表现为正常测试失败；人工完整样本可使用日历生成日期，已知期末100/110，独立假期与 DST 断言不能从生产日历生成预期。
  ```python
  def test_monthly_ratio():
      from portfolio.data.daily_monthly import aggregate_daily_prices
      result = aggregate_daily_prices(prices, symbol='SPY', start_month='2025-01', end_month='2025-01', confirmed=True, as_of='2025-02-02T00:00:00Z')
      assert result.returns.iloc[0].local_return == pytest.approx(.1)
  ```
- [x] 运行 `.venv/bin/python -m pytest tests/test_daily_monthly.py -q`，保存 RED 与失败原因。覆盖设计的失败案例、官方日期、缓存损坏/身份/partial、输入不修改及不联网。
- [x] 实现三份核心；必要时将纯验证辅助函数放同职责模块，避免全量重构。用 DataBundle 临时承载合法月末价格，并调用 build_local_returns，不重新写收益公式。返回表包含所有阻止月份及 NaN；不让报表标签代替可用性认证。
- [x] 固定依赖新增 exchange_calendars==4.13.2、korean_lunar_calendar==0.4.0、pyluach==2.3.0、toolz==1.2.0、tzdata==2026.5；不改变旧依赖版本。
- [x] 同一命令 GREEN，再运行 `.venv/bin/python -m pytest tests/test_returns.py tests/test_updates.py tests/test_daily_monthly.py -q`；自审、报告 outputs/acceptance/S04C1/task-1-report.md，交给审查者验收。

### Task 2: 三步操作页面与状态检查

**Files:** 新建 app/views/daily_monthly.py、tests/test_daily_monthly_view.py；修改 app/main.py；需要的人工样本函数可放 src/portfolio/data/daily_monthly_samples.py。

**Interfaces:** 使用 Task1 函数；downloads_root 遵守 PORTFOLIO_DOWNLOADS_ROOT，所有会话键 dm_。页面标题／侧栏「日线月度查验」。s['dm_result'] 只保留当前有效 DailyMonthlyResult，s['dm_token'] 输入指纹，缓存 manifest 变化失败关闭。

- [x] 写 AppTest 失败检查，默认无结果/无网络；完整人工100→110；未确认阻止；改参数撤下结果；缺最后和中间报价；缓存只读及损坏后无结果导出；跨页不改 bundle。以真实核心为主，仅拦截网络调用，不模拟整个核心。
  ```python
  at.radio(key='workspace').set_value('日线月度查验').run()
  at.checkbox(key='dm_confirm').check().run()
  at.button(key='dm_compute').click().run()
  assert at.session_state['dm_result'].returns.iloc[0].local_return == pytest.approx(.1)
  ```
- [x] 运行 `.venv/bin/python -m pytest tests/test_daily_monthly_view.py -q` 保存 RED。
- [x] 按页面「1 选择来源 → 2 产品与月份 → 3 查验结果」实现。来源 radio dm_mode=['人工案例','已下载缓存']；案例 dm_case=['完整报价','缺最后交易日','缺月中交易日','重复日期']；dm_symbol 六个价格代码（默认SPY），缓存仅列可诊断的 success/partial 且有 raw_file 项；dm_run 可选已有 schema1 版本，损坏记录显示中文错误不静默消失。dm_start_month/dm_end_month 默认2025-01；dm_confirm 默认False；dm_compute 文案「查验日线并计算月收益」。人工价格前月100、本月110，案例固定Dec2024/Jan2025，修改月份应生成该目标月份的同样人工规则，保持人工标签；未来月受成熟规则阻止。
- [x] 先中文指标（目标月数／可预览收益月数）、月末及收益百分比表、逐月中文阻止原因，再 expander「逐日明细与来源证据」含三张完整表、metadata JSON和CSV下载。USD 保持原币明确显示；每次重新渲染重新验证真实缓存和manifest，缓存指纹包括root及manifest与输入。参数变化后无旧结果和下载。提示看一月收益须下载完整2024-12-01至2025-02-01；本页不下载、不自动提交。保持原 Material 字体修复，不加全局 CSS。
- [x] GREEN `.venv/bin/python -m pytest tests/test_daily_monthly_view.py tests/test_hkd_returns_view.py tests/test_downloads_view.py -q`；报告 outputs/acceptance/S04C1/task-2-report.md 并审查。

### Task 3: 真实样本、独立复算与交付

**Files:** scripts/verify_daily_monthly.py、tests/test_daily_monthly_verification.py；outputs/acceptance/S04C1/README.md、checks.txt、progress.md；README.md 与总流程状态。

- [x] TDD 写离线验证器：--run-id 或明确 --s01-manifest 二选一，只读取既有快照。产品SPY/2800.HK分别输出原始两端日期、价格、直接比值、生产输出、是否一致与阻止状态；先验证全部快照哈希，不自行下载。已知100/110断言独立比值，端点缺失保持诊断且收益NaN。保存验证器 RED/GREEN。执行依据：新在线下载失败后，复用已核验的 S01 旧证据作独立离线诊断，不冒充在线成功。
- [x] 显式调用现有 run_update 下载 SPY/2800.HK，2024-12-01≤date<2025-02-01，一次一项无重试，保存 run_id 与逐项状态。失败仍保留记录，不伪造在线成功。
- [x] 运行 `.venv/bin/python scripts/verify_daily_monthly.py --run-id 20261016T132413936814Z-c784827343704f318c02d12381d2abbb --output outputs/acceptance/S04C1/online_attempt`：完整性通过、来源不可用退出1。以 --s01-manifest 入口独立离线复算成功，三张表、metadata 与 JSON 保存 legacy_replay；旧快照仅只读，全文件SHA256核验。
- [x] 运行 `.venv/bin/python -m pytest -q`，最终360项通过，两个上游弃用提示已记录。更新验收状态、总流程和简单用户操作说明；重新安装本地包、重启核实身份的Streamlit服务，健康检查200；最终宽窄屏及CSV/撤下结果通过。
- [x] 整体独立审查Approved；原始布尔复权价转换前拒绝，True/False两项RED→GREEN54项复查通过，最终全套360项通过。只将C1标为交付，C2/C3仍未完成，下一步为FX配对及HKD连接。
