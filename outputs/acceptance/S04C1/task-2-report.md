# S04-C1 Task 2 — 三步日线月度查验页面

## 交付

- 新建 `app/views/daily_monthly.py`、`tests/test_daily_monthly_view.py`，修改 `app/main.py` 注册「日线月度查验」。未修改核心、下载器、其他页面或 DataBundle。
- 页面按「1 选择来源 → 2 产品与月份 → 3 查验结果」展开，只有一个主要计算按钮，默认人工案例、不自动计算、不联网、不保存。
- 人工案例使用真实交易日历和真实聚合函数，默认前月 100、本月 110，确认后得到 10% 原币收益。变更目标月份会重建对应月份的合成报价；支持缺末日、缺月中日、重复日案例。
- 缓存模式只列 schema1 快照，产品限六个价格代码、success/partial 且有 raw_file；损坏记录显示中文错误。每次 rerender 通过真实 `cached_monthly_prices` 重读验证完整快照与原始 JSON。
- `dm_token` 包含下载根目录、完整已验证 manifest、来源、案例、版本、产品、月份和确认状态。输入或 manifest 变化会撤下结果和下载，损坏失败关闭。`dm_result` 只保存当前 DailyMonthlyResult。
- 先展示中文目标月数／可预览收益月数、月末价格和百分数收益及逐月原因；完整三表、metadata JSON、三个 CSV 及 JSON 下载放在折叠区。USD 明确保留原币，历史可得资格为 False，available_at 由核心保持为空。
- 保留原页面 Material 字体处理；未添加 CSS、依赖或网络路径。

## RED / GREEN

先写 6 个 AppTest 检查，再运行 `.venv/bin/python -m pytest tests/test_daily_monthly_view.py -q`。六项均在设置工作页面时因导航尚无「日线月度查验」失败，证明新增页面缺失：`task-2-red.log`。

实现后初次同一测试集为 **6 passed**：`task-2-green-initial.log`。补充未来月份、确认撤销、根目录变化和空缓存覆盖后，运行指定回归：

```text
.venv/bin/python -m pytest tests/test_daily_monthly_view.py tests/test_hkd_returns_view.py tests/test_downloads_view.py -q
20 passed in 3.73s
```

完整输出：`task-2-green.log`。

## 已验证行为

AppTest 使用真实页面和核心聚合／缓存加载，仅拦截 Yahoo 网络函数。缓存测试通过真实 `run_update` 和离线 RawResponse 写入独立临时目录，再用真实页面读取；未模拟核心结果。

- 默认无结果、无下载、无网络；确认后完整人工样本收益为 0.1。
- 未确认、缺最后日、缺中间日、重复日和未来月份均阻止收益。
- 改月份、撤销确认、切换根目录、改 manifest、破坏原始缓存均撤下旧结果与下载。
- 缓存计算前后文件字节不变；缓存损坏显示中文错误且无导出。
- 跨页返回数据导入不改变已有 bundle；原港币收益页面及下载页面回归通过。

## 自审及限制

已逐段复核输入失效路径、缓存读取失败路径、来源身份及 manifest 绑定、六产品过滤、百分比显示与 CSV 小数口径、无 DataBundle 写入及原导航兼容性。未发现阻止交付问题。

此报告的界面验证为 Streamlit AppTest；未启动人工浏览器或真实联网下载。真实样本独立核对与总体验收由父任务负责。本页面只提供当前版本原币预览，不提供港币换算或历史资格认证。

## 文案复核补充

为共享收益计算器的 `invalid_value` 阻止原因添加中文显示「收益计算超出有限数值范围」。这是文案映射调整。再次运行 `.venv/bin/python -m pytest tests/test_daily_monthly_view.py -q`：**8 passed in 1.81s**，完整输出见 `task-2-copy-green.log`。当前文件收集为 8 项测试（参数化缺失案例计三项），初始 RED 的 6 项及后续 20 项指定回归记录保持原始实测结果。

## 审查补充：固定未来月份测试时钟

Task2 审查批准后，修正未来月份测试的时间依赖：仅在该测试中用薄委托把 `as_of='2026-10-16T00:00:00Z'` 传给真实聚合函数，人工样本校验和最终计算均使用该时间。未修改生产代码，也未模拟核心计算结果。再次运行指定页面测试：**8 passed in 1.93s**，见 `task-2-deterministic-green.log`。
