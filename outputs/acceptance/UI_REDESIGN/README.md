# 研究工作台 UI 重设计验收

日期：2026-10-17。设计规格与实施计划位于 `docs/superpowers/`。本目录保留新版 UI 的实际验收产物；此前 S02–S06 的验收目录是历史交付记录。

## 使用入口

日常工作台：<http://127.0.0.1:8502>。默认打开研究总览。独立浏览器验收使用 8504，临时通过 `PORTFOLIO_IMPORTS_ROOT=outputs/acceptance/S02/bundles` 只读打开已有真实日线版本；没有点击导入提交或触发联网下载。

| 页面／路由 | 实际实现 |
| --- | --- |
| 研究总览 / overview | 只读状态、确定下一步、人工演示入口 |
| 01 准备数据 / prepare_data | 原导入、字段映射、质量检查、本地版本 |
| 02 核对资格 / eligibility | 资格中心及现有工具链接 |
| 03 筛选候选 / screen_candidates | 共用研究输入、范围、K/N、筛选导出 |
| 04 收益与风险 / risk_preview | 同一输入和筛选状态、权重、现有风险计算与导出 |
| 市场数据与缓存 / downloads | 原下载及缓存工具 |
| 收益与窗口核对 / returns_window | 原港币收益工具，链接共同窗口与日线工具 |
| 历史资格与来源 / history_sources | 原历史资格工具 |
| 利率与因子 / rates_factors | 原港币利率工具，链接因子与官方汇率 |
| alignment / daily_monthly / daily_hkd / reference_downloads | 原独立工具，快速跳转可直接到达 |

导航保留 `workspace` 中文值的交接兼容。侧栏流程组可收起；快速跳转始终可见，打开下拉框并选择即可到达任意工具。各页提供返回研究总览入口。

## 自动检查

新增状态、导航、资格中心、工具上传往返测试；既有页面测试仅迁移导航入口和分离风险入口，保留数值、失效、离线、缓存与导出断言。完整测试最终输出保存在 `full_test_checks.txt`。

最终完整回归：**736 passed, 2 warnings in 226.77s (0:03:46)**。两条提示来自现有 `exchange_calendars` 的 NumPy 时间单位弃用；没有失败。最终针对性回归：**45 passed in 99.23s (0:01:39)**，见 `targeted_test_checks.txt`。

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m pytest tests/test_workspace_state.py tests/test_workspace_shell_view.py tests/test_eligibility_hub_view.py tests/test_tool_navigation_uploads.py tests/test_candidate_screening_view.py tests/test_risk_workspace_view.py -q
```

独立只读审查发现并修复：核对工具上传在跨页后丢失、工具页状态晚一轮更新。修复后审查未发现剩余重要问题；状态条在本轮输入失效／计算后读取状态。普通控件使用当前锁定 Streamlit 的会话保留能力；上传副本单独保存并按候选 epoch 或工具来源上下文绑定，提供显式清除。

## 浏览器证据

执行脚本：`scripts/verify_workspace_redesign_browser.mjs`，连接本机 Chromium CDP 9224。复现完整真实版本路径：

```bash
PORTFOLIO_IMPORTS_ROOT=outputs/acceptance/S02/bundles .venv/bin/python -m streamlit run app/main.py --server.address 127.0.0.1 --server.port 8504 --server.headless true --browser.gatherUsageStats false
WORKSPACE_UI_URL=http://127.0.0.1:8504/ WORKSPACE_REAL_VERSION=s01-prices-b8912ef9e8e943e0bd6b8cf22e4f3b32 node scripts/verify_workspace_redesign_browser.mjs
```

`browser_checks.json` 保存实测日期、各宽度结果、导出字节数、上传往返及真实 N=0。截图覆盖总览、准备数据、资格中心、候选筛选、风险预览、下载工具及真实 N=0 总览，宽度为 1440／720／390。检查页面级横向溢出、可视区文字重叠和页面异常；表格／热图允许容器内滚动。截图另由人工视检核对。固定工具栏下方留出页首空间，图标字体不作全局覆盖。

最终浏览器输出：**27 项检查**，实测 UTC `2026-10-17T15:31:11.656Z`（香港 23:31）。21 个页面／宽度组合没有页面级溢出、可视区文字重叠或页面异常；实际导出 `risk_evidence.json` 为 **18,823 字节**。浏览器原生删除权重文件会撤下风险结果；随后重新上传另一文件名的相同权重、计算并跨页返回，结果保留；清除保留副本后再次失效。

实际走通：人工风险演示 → N100/K30 → 风险预览 → 下载 `risk_evidence.json`（非空，target_k=30，portfolio_constructed=false）→ 总览 → 风险页；真实上传权重往返保留，显式清除后风险结果撤下。只读打开真实日线版本 → 重新筛选 N=0 → 总览明确提示需要月度准备。产物包括 `browser_weights.csv`、`risk_evidence.json` 与各页面截图。

上传测试保留原有数值、来源散列与失效断言。旧港币收益测试的上传传输替身现显式模拟原生删除的 `on_change` 回调，以区分“用户删除文件”与“因跨页而暂未挂载控件”；四项新增工具测试验证往返保留及显式清除。

## 口径和限制

本次只改展示、导航和会话文件保留；没有修改 `src/portfolio/` 的计算或合同。工具仍独立核对，不自动生成已认证月度资料。数量通过和风险预览不认证历史候选池；实际 K 项成员选择、utility、做空、CAPM／FF 模型及优化仍待后续阶段。人工案例始终标记 SYNTH。

原阶段浏览器脚本保留作历史验收记录；新版 UI 应使用本目录对应的新脚本。项目没有 Git 仓库，本次直接保留工作目录中的实现，没有提交、合并或发布外部网站。
