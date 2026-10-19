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


## Task 3: 独立复算及交付验收

**Files:** Create `scripts/verify_daily_hkd.py`, `tests/test_daily_hkd_verification.py`；Update README、workflow、outputs/acceptance/S04C2/README.md/progress.md/checks.txt。

**Consumes:** 既有 C1 `verify_legacy` 和 S01 `load_verified_manifest` 作为旧价证据；Task1 connector；S01 raw Yahoo FX。

**Produces:** `.venv/bin/python scripts/verify_daily_hkd.py --s01-manifest outputs/acceptance/S01/snapshots/20261012T143920Z-6f4d426f/snapshot_manifest.json --output outputs/acceptance/S04C2/legacy_replay`；人工及SPY/2800.HK Jan2025真实离线证据。生产与独立结果需数值/日期一致，不满足exit1，损坏raise/exit1。

- [ ] 先写测试：独立手算、旧raw哈希损坏拒绝、生产结果被改写要识别、缺端点诊断。RED后实现；直接json读取日期/close，用ZoneInfo重建实际日、独立monthend筛选、年龄及ratio，不能调用生产FX端点来算参考值。旧快照全历史partial仍保留，仅显式本窗口端点预览，metadata source_mode=legacy_offline_replay,current_vintage,source_manifest_hash/rawsha。
- [ ] 验证接口 `verify_legacy_hkd(manifest_path)->(report,tables)`；保存 raw证据端点参考、fx_endpoints.csv、fx_observations.csv、各symbol reconciliation和metadata、independent_verification.json。报告中包含source manifest/rawsha、sourceglobalstatus和endpointscope，不能冒充success快照。不新下载。
- [ ] 运行focused GREEN，独立复算及完整 `.venv/bin/python -m pytest -q`；所有检查通过后标准重装本包（不改依赖），重启已核实项目Streamlit进程。
- [ ] 实际浏览器宽1440/窄720展示及下载CSV检查；确认成功港币11.410256%、取消确认撤下结果、缺汇率失败、无多余网络请求；记录可做与未做。页面HTTP健康200；副本diff及独立最终代码审查，所有Important/Critical修复并重验受影响测试。
- [ ] 更新用户三步操作、值和失败例、当前局限、下步C3；检查文档链接、锁依赖未改、旧缓存哈希仍通过。记录fulltest数，不虚报在线成功/历史资格；本步通过后结束。

Design: docs/superpowers/specs/2026-10-17-s04c2-daily-hkd-design.md
