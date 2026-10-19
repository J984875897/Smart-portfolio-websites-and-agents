# S04-C2 Daily FX and HKD Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

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

## Task 1: FX 端点、港币连接与缓存

**Files:** Create `src/portfolio/data/daily_hkd.py`, `src/portfolio/data/fx_cache.py`, `tests/test_daily_hkd.py`, `tests/test_fx_cache.py`.

**Interfaces:** `DailyHkdResult(prices,fx_observations,fx_endpoints,reconciliation,metadata)`；`connect_daily_hkd(prices,fx_frame=None,*,fx_confirmed=False,max_age_days=7)`；`cached_daily_fx(root,run_id)->DataFrame`。具体数据语义见设计文件全文。

- [x] 写 tests 并运行 RED 日志到 task-1-red.log。最低手算测试：

```python
result = connect_daily_hkd(price_result, pd.DataFrame([
    dict(date='2024-12-31',currency='USD',hkd_per_unit=7.8,source_name='SYNTH'),
    dict(date='2025-01-31',currency='USD',hkd_per_unit=7.9,source_name='SYNTH'),
]), fx_confirmed=True)
row = result.reconciliation.iloc[0]
assert row.hkd_return == pytest.approx(1.1*7.9/7.8-1)
assert row.fx_start_observed_date == '2024-12-31'
assert row.historical_eligible == False
```

- [x] 实现端点逐行诊断：输入 date/currency/hkd_per_unit/source_name 必须存在且列唯一，非 USD 拒绝；原始输入行号/hash/file/sheet 保留，非法日期全阻止；月内最大日期全部行必须恰一条且数值有限正/非bool/来源非空。端点输出 `date`（自然月末）、`observed_date`、`age_days`、`hkd_per_unit`、`status`、`reason` 和来源列。年龄超限 blocked；empty/missing 月输出 blocked。fx_confirmed 与 source_status 在连接中阻止，不隐藏诊断。
- [x] 复用 S03 公式：用 C1 valid local_return 建 temporary DataBundle total_return 月频；合格端点以自然月末日期交给 reconcile_hkd。按 date 对回每一个 C1 目标行，保留 C1 原始 blocked；HKD 不需要 FX；USD FX 缺失/invalid/陈旧/partial/unconfirmed 带起止原因，hkd_return NaN；保持 fx_return/cross_term/价格和汇率来源。`metadata` 保存两类来源、原字节哈希/manifest、政策、确认、preview 限制。不得就地改 C1 或 FX 输入。
- [x] 缓存：full load_snapshot/read_artifact；schema1只选HKD=X一项，success/partial且raw；核对 meta symbol/currency/instrumentType/timezone，转换前拒绝raw close布尔；parse_yahoo_chart 后用close并按manifest区间筛选，source明确Yahoo非官方。schema2只选HKMA_USDHKD，success/partial且raw；HTTP200全部page按原顺序重parse_page，核对日期递增、无重叠、区间合法、page metadata offset递增/页长度、pagination_complete所述完整性；原usd布尔拒绝。坏末页/非200不静默当success；partial可拒绝不可解析证据。attrs至少source_name/source_hash/source_status/manifest/run_id/unit/available_at/historical_eligible；HKMA多raw哈希组合用确定性顺序，保留逐页哈希。
- [x] 覆盖年龄边界/周末/不跨月/最新坏值/重复/非法日期/zero,bool,inf/币种/confirmation/local blocked/HKD无FX/溢出/不变性；缓存用真实固定fetch模拟构造 immutable快照，验证success/partial/identity/rawbool/hash/unavailable/分页/no mutation。
- [x] Run `.venv/bin/python -m pytest tests/test_daily_hkd.py tests/test_fx_cache.py tests/test_fx.py tests/test_daily_monthly.py -q` 保存 GREEN；自查及任务报告 task-1-report.md。审查通过后勾选。

## Task 2: 三步查验界面

**Files:** Create `app/views/daily_hkd.py`, `src/portfolio/data/daily_hkd_samples.py`, `tests/test_daily_hkd_view.py`；Modify `app/main.py` only append page branch/list。

**Consumes:** Task1公开接口；C1 cached_monthly_prices/aggregate_daily_prices；existing read_file, trading_schedule,list_runs/load_snapshot。

**Produces:** 新侧栏「日线港币查验」；session keys `dh_*`；`dh_result`为DailyHkdResult或None；`dh_compute`按钮「查验并计算港币收益」。

- [x] 先写 AppTest 默认无结果/无下载、两确认成功、缺期末/过旧/重复失败、参数确认失效、空缓存、root变化、缓存损坏撤下导出、不联网和不变DataBundle，保存 RED。
- [x] sample数据独立核心helper：`sample_daily_prices(symbol,start_month,end_month,case='完整报价')` 使用真实交易日100×1.1^月差，缺末日报价案例；`sample_daily_fx(start_month,end_month,case='完整汇率')` 每月末7.8+0.1×月差，缺期末月/过旧(末日-8天)/重复末日案例。验证月份复用C1；来源标SYNTH，不依赖app模块。
- [x] 页面三步：1价格（人工/缓存，symbol/起止月）；2USD汇率（人工/缓存/CSV或XLSX及工作表；明确HKMA官方/Yahoo非官方）；3结果。HKD无必需FX控件。两个确认默认false；年龄number_input整数0..7默认7；合成输入说明10%和7.8→7.9。read_file保留attrs；模板下载在说明折叠里，可用字段完整两行CSV。
- [x] 所有模式参数、文件bytes/name/sheet、rootresolve、manifest及确认纳入token，变更清空。每次渲染重新验证所选价格/FX缓存，异常清空、显示中文、禁compute；点击后才计算。不得有自动网络/保存/交接操作。errors使用项目已有预期异常集合并处理read_file错误。
- [x] 摘要显示目标月数/可预览港币月数；表显示目标月、local%/FX%/cross%/HKD%、中文原因；证据表并列实际价格和FX起止日期及年龄。折叠原始sessions/monthly、FX诊断/endpoints/reconciliation及metadata，下载CSV/JSON。说明max7研究假设、异步估值、当前版本非历史资格；不改现有CSS。
- [x] Run `.venv/bin/python -m pytest tests/test_daily_hkd_view.py tests/test_daily_monthly_view.py tests/test_smoke.py -q` 保存GREEN和task-2-report.md；任务审查通过勾选。

## Task 3: 独立复算及交付验收

**Files:** Create `scripts/verify_daily_hkd.py`, `tests/test_daily_hkd_verification.py`；Update README、workflow、outputs/acceptance/S04C2/README.md/progress.md/checks.txt。

**Consumes:** 既有 C1 `verify_legacy` 和 S01 `load_verified_manifest` 作为旧价证据；Task1 connector；S01 raw Yahoo FX。

**Produces:** `.venv/bin/python scripts/verify_daily_hkd.py --s01-manifest outputs/acceptance/S01/snapshots/20261012T143920Z-6f4d426f/snapshot_manifest.json --output outputs/acceptance/S04C2/legacy_replay`；人工及SPY/2800.HK Jan2025真实离线证据。生产与独立结果需数值/日期一致，不满足exit1，损坏raise/exit1。

- [x] 先写测试：独立手算、旧raw哈希损坏拒绝、生产结果被改写要识别、缺端点诊断。RED后实现；直接json读取日期/close，用ZoneInfo重建实际日、独立monthend筛选、年龄及ratio，不能调用生产FX端点来算参考值。旧快照全历史partial仍保留，仅显式本窗口端点预览，metadata source_mode=legacy_offline_replay,current_vintage,source_manifest_hash/rawsha。
- [x] 验证接口 `verify_legacy_hkd(manifest_path)->(report,tables)`；保存 raw证据端点参考、fx_endpoints.csv、fx_observations.csv、各symbol reconciliation和metadata、independent_verification.json。报告中包含source manifest/rawsha、sourceglobalstatus和endpointscope，不能冒充success快照。不新下载。
- [x] 运行focused GREEN，独立复算及完整 `.venv/bin/python -m pytest -q`；所有检查通过后标准重装本包（不改依赖），重启已核实项目Streamlit进程。
- [x] 实际浏览器宽1440/窄720展示及下载CSV检查；确认成功港币11.410256%、取消确认撤下结果、缺汇率失败、无多余网络请求；记录可做与未做。页面HTTP健康200；副本diff及独立最终代码审查，所有Important/Critical修复并重验受影响测试。
- [x] 更新用户三步操作、值和失败例、当前局限、下步C3；检查文档链接、锁依赖未改、旧缓存哈希仍通过。记录fulltest数，不虚报在线成功/历史资格；本步通过后结束。
