# S04-C3 本地观测版本时间资格验收

本步交付下载完成时点、重验快照证据、逐行资格判断，以及「历史资格查验」页面。用户已确认的 [设计](../../../docs/superpowers/specs/2026-10-17-s04c3-time-eligibility-design.md) 与 [执行计划](../../../docs/superpowers/plans/2026-10-17-s04c3-time-eligibility-implementation.md) 为验收边界。

## 已验证

- Yahoo 与 reference 下载器在所有原始文件及派生文件写入后记录 completed_utc；created_utc 保持开始时间。旧快照不回填，仍可读取；新字段须 UTC 且不早于开始。
- 决策时点含时区、可以与完成时间相等；早一微秒阻止。来源 partial、缺快照、缺完成时点、错误散列、基础收益失败均阻止。USD 需要价格和 FX，HKD 只需价格。
- 人工声明最多 declaration_only；不升级 historical_observation_eligible。historical_universe_eligible 始终 false，C2 原始字段和输入保持不变。
- 离线模拟完整下载链路分别覆盖 Yahoo FX 与 HKMA FX 的散列绑定；重新读取发现损坏后撤下页面结果及导出。
- AppTest 覆盖无 C2、SYNTH 边界、无效时间、声明、C2 来源与文件损坏，以及导入 bundle 不变。查验页每次重算，无保存或联网路径。

## 验证命令与结果

2026-10-17 本地运行：

```bash
.venv/bin/python -m pytest -q
```

474 passed，2 条 exchange_calendars 上游弃用警告。新增时间字段、核心及页面测试均先观察到预期失败，再实现通过。原 C1/C2 破坏测试相应更新：无效开始时间使缓存不可用，恢复合法清单后重新选择并计算，再检查原始文件破坏。

独立只读复核未发现 Critical / Important 问题，另运行 100 项针对测试通过。发现一项 Minor：极端年份转 UTC 可溢出；已先复现失败，再统一转换为输入错误，增加两项核心案例及页面验证。上述 474 项全套结果包含该修正。

已运行本地包无依赖重装，并验证从 `.venv/lib/python3.14/site-packages/portfolio/data/time_eligibility.py` 导入。工作台重启后继续提供 http://127.0.0.1:8501。

浏览器验证脚本：`node scripts/verify_time_eligibility_browser.mjs`（需要隔离 Chrome 的本机 9224 CDP）。[机器记录](browser_checks.json)显示 1440/720 两种宽度均无页面横向溢出、无异常、通过月数 1、导出按钮 2；[宽屏截图](browser_1440.png)、[窄屏截图](browser_720.png)可供人工查看。窄屏表格保留内部横向滚动。

## 使用与限制

左侧「历史资格查验」→「SYNTH 时间案例」可直接体验。默认完成及决策时间同为 2025-02-02 00:00 UTC；决策改早一微秒后变为 0 个月通过。真实查验先在 C2 计算，返回本页选择「上一页日线港币结果」。CSV 保留小数收益与原始资格字段，新增观测时间资格独立列；JSON 包含预期与实际来源散列、run_id、完成时间。

本次没有自动下载或修改既有数据。旧真实缓存缺完成时间时必须时间证据不足。离线模拟下载不是新的在线可用性证明。完成记录证明本地最晚已取得该版本，依赖本地时钟和清单，未经独立时间戳认证；不证明源站历史发布时间或历史候选池完整。C3 不接入 S03 共同窗口，也不形成候选 N。历史 universe、幸存者偏差和 S04 总体验收仍待后续步骤。
