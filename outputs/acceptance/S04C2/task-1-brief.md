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


## Task 1: FX 端点、港币连接与缓存

**Files:** Create `src/portfolio/data/daily_hkd.py`, `src/portfolio/data/fx_cache.py`, `tests/test_daily_hkd.py`, `tests/test_fx_cache.py`.

**Interfaces:** `DailyHkdResult(prices,fx_observations,fx_endpoints,reconciliation,metadata)`；`connect_daily_hkd(prices,fx_frame=None,*,fx_confirmed=False,max_age_days=7)`；`cached_daily_fx(root,run_id)->DataFrame`。具体数据语义见设计文件全文。

- [ ] 写 tests 并运行 RED 日志到 task-1-red.log。最低手算测试：

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

- [ ] 实现端点逐行诊断：输入 date/currency/hkd_per_unit/source_name 必须存在且列唯一，非 USD 拒绝；原始输入行号/hash/file/sheet 保留，非法日期全阻止；月内最大日期全部行必须恰一条且数值有限正/非bool/来源非空。端点输出 `date`（自然月末）、`observed_date`、`age_days`、`hkd_per_unit`、`status`、`reason` 和来源列。年龄超限 blocked；empty/missing 月输出 blocked。fx_confirmed 与 source_status 在连接中阻止，不隐藏诊断。
- [ ] 复用 S03 公式：用 C1 valid local_return 建 temporary DataBundle total_return 月频；合格端点以自然月末日期交给 reconcile_hkd。按 date 对回每一个 C1 目标行，保留 C1 原始 blocked；HKD 不需要 FX；USD FX 缺失/invalid/陈旧/partial/unconfirmed 带起止原因，hkd_return NaN；保持 fx_return/cross_term/价格和汇率来源。`metadata` 保存两类来源、原字节哈希/manifest、政策、确认、preview 限制。不得就地改 C1 或 FX 输入。
- [ ] 缓存：full load_snapshot/read_artifact；schema1只选HKD=X一项，success/partial且raw；核对 meta symbol/currency/instrumentType/timezone，转换前拒绝raw close布尔；parse_yahoo_chart 后用close并按manifest区间筛选，source明确Yahoo非官方。schema2只选HKMA_USDHKD，success/partial且raw；HTTP200全部page按原顺序重parse_page，核对日期递增、无重叠、区间合法、page metadata offset递增/页长度、pagination_complete所述完整性；原usd布尔拒绝。坏末页/非200不静默当success；partial可拒绝不可解析证据。attrs至少source_name/source_hash/source_status/manifest/run_id/unit/available_at/historical_eligible；HKMA多raw哈希组合用确定性顺序，保留逐页哈希。
- [ ] 覆盖年龄边界/周末/不跨月/最新坏值/重复/非法日期/zero,bool,inf/币种/confirmation/local blocked/HKD无FX/溢出/不变性；缓存用真实固定fetch模拟构造 immutable快照，验证success/partial/identity/rawbool/hash/unavailable/分页/no mutation。
- [ ] Run `.venv/bin/python -m pytest tests/test_daily_hkd.py tests/test_fx_cache.py tests/test_fx.py tests/test_daily_monthly.py -q` 保存 GREEN；自查及任务报告 task-1-report.md。审查通过后勾选。


Design: docs/superpowers/specs/2026-10-17-s04c2-daily-hkd-design.md
