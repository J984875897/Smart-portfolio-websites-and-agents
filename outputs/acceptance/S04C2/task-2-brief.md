# S04-C2 Daily FX and HKD Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 从可复查日线端点预览港币月收益，成功和阻止都有可核对证据。

**Architecture:** C1 价格结果经独立 FX 端点模块连接 S03 reconcile_hkd；缓存只读原始响应；三步 Streamlit 页调用核心；独立验收直接复算原始 JSON。

**Tech Stack:** 现有 Python 3.14、pandas、Streamlit、pytest；不新增或升级依赖。

## Global Constraints

- 本轮只交付 S04-C2；C3 历史可得性、S05 候选数及组合仍未交付。
- 仅六个 C1 价格样本；只转换 USD→HKD，HKD 产品固定 1。
- FX 单位固定每美元兑港币，不求倒数；max_age_days 整数 0–7，默认 7，等于允许。
- 自然月末标签与实际价格/FX 日期分别保存；FX 不跨月、不使用未来、不退过最新坏行、不填补完整日历。
- 两个确认必须严格 True；价格 blocked 不能变 valid；partial 源只诊断，不能 USD 换算。
- available_at=''，historical_eligible=False；日期和下载时间不冒充历史可得性。
- 参数、文件、工作表、确认、目录、manifest 或源字节变化撤下旧结果和下载；重渲染复核缓存。
- 只读既有数据，不联网、不保存 DataBundle、不引入 paid/key、不改原始快照。
- 使用现有 reconcile_hkd 换算公式；不在 UI 重复金融公式；保持旧接口和七页兼容。
- 本目录无 Git；基线目录见 outputs/acceptance/S04C2/backup.txt，生成 diff 代替 commit。


## Task 2: 三步查验界面

**Files:** Create `app/views/daily_hkd.py`, `src/portfolio/data/daily_hkd_samples.py`, `tests/test_daily_hkd_view.py`；Modify `app/main.py` only append page branch/list。

**Consumes:** Task1公开接口；C1 cached_monthly_prices/aggregate_daily_prices；existing read_file, trading_schedule,list_runs/load_snapshot。

**Produces:** 新侧栏「日线港币查验」；session keys `dh_*`；`dh_result`为DailyHkdResult或None；`dh_compute`按钮「查验并计算港币收益」。

- [ ] 先写 AppTest 默认无结果/无下载、两确认成功、缺期末/过旧/重复失败、参数确认失效、空缓存、root变化、缓存损坏撤下导出、不联网和不变DataBundle，保存 RED。
- [ ] sample数据独立核心helper：`sample_daily_prices(symbol,start_month,end_month,case='完整报价')` 使用真实交易日100×1.1^月差，缺末日报价案例；`sample_daily_fx(start_month,end_month,case='完整汇率')` 每月末7.8+0.1×月差，缺期末月/过旧(末日-8天)/重复末日案例。验证月份复用C1；来源标SYNTH，不依赖app模块。
- [ ] 页面三步：1价格（人工/缓存，symbol/起止月）；2USD汇率（人工/缓存/CSV或XLSX及工作表；明确HKMA官方/Yahoo非官方）；3结果。HKD无必需FX控件。两个确认默认false；年龄number_input整数0..7默认7；合成输入说明10%和7.8→7.9。read_file保留attrs；模板下载在说明折叠里，可用字段完整两行CSV。
- [ ] 所有模式参数、文件bytes/name/sheet、rootresolve、manifest及确认纳入token，变更清空。每次渲染重新验证所选价格/FX缓存，异常清空、显示中文、禁compute；点击后才计算。不得有自动网络/保存/交接操作。errors使用项目已有预期异常集合并处理read_file错误。
- [ ] 摘要显示目标月数/可预览港币月数；表显示目标月、local%/FX%/cross%/HKD%、中文原因；证据表并列实际价格和FX起止日期及年龄。折叠原始sessions/monthly、FX诊断/endpoints/reconciliation及metadata，下载CSV/JSON。说明max7研究假设、异步估值、当前版本非历史资格；不改现有CSS。
- [ ] Run `.venv/bin/python -m pytest tests/test_daily_hkd_view.py tests/test_daily_monthly_view.py tests/test_smoke.py -q` 保存GREEN和task-2-report.md；任务审查通过勾选。


Design: docs/superpowers/specs/2026-10-17-s04c2-daily-hkd-design.md
