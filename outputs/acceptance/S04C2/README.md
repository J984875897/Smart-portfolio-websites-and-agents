# S04-C2：日线汇率端点与港币收益

状态：**S04-C2开发验收通过**。日期：2026-10-17。

本步将上一阶段日历价格诊断与实际日线汇率端点连接，预览 HKD 月收益。保留自然月末标签、真实价格日、真实 FX 日及陈旧天数。历史可得认证 C3、正式候选数量与组合配置不在本步范围。

设计见[口径说明](../../../docs/superpowers/specs/2026-10-17-s04c2-daily-hkd-design.md)，实施与检查见[本步计划](../../../docs/superpowers/plans/2026-10-17-s04c2-daily-hkd-implementation.md)、[进度](progress.md)。

人工完整案例预期：100→110 原币收益10%；每美元兑港币7.8→7.9，港币收益 `(110/100)*(7.9/7.8)-1 = 11.4102564103%`。其中汇率收益1.2820512821%，交叉项0.1282051282%。人工数值用于验证公式。

默认允许 FX 距自然月末最多7个日历日（可调0–7、等于允许），这是研究假设，不是官方保证。仅使用该月最后一条观察，最新坏值、重复或缺月时阻止，不退回更早有效值。价格与 FX 不保证同时成交；日期和下载时间不能充当历史发布时间。

本轮不新增在线请求，真实计算使用已验证的 S01 原始响应离线重放；不宣称新的在线成功。既有 HKMA 在线失败仍保留，Yahoo 不自动冒充官方来源。

## 在工作台检查

打开 [本地工作台](http://127.0.0.1:8501)，左侧选「日线港币查验」。

1. 价格选「人工案例／完整报价」，SPY，起止均为2025-01；勾选复权确认。
2. 汇率选「人工案例／完整汇率」，勾选每美元兑港币确认，最大年龄7。
3. 点「查验并计算港币收益」：可预览1个月，港币收益11.4103%。

「缺期末月」「过旧」「重复末日」分别阻止缺月、8日陈旧报价（超过7日上限）和重复报价；7日为边界仍允许。取消确认或改变任意输入后旧结果撤下，须重新点击。价格缺最后交易日也阻止；2800.HK人工完整报价直接输出10%，不用美元汇率。

汇率可以选HKMA官方缓存、Yahoo非官方缓存、CSV/XLSX文件并选工作表；[导入格式](../../../docs/data/daily_fx_format.md)及页面模板可参考。页面只读，既有一月缓存缺前月时不会伪造端点。完整1月收益需要前月价格和FX，下载区间建议2024-12-01至2025-02-01（结束不含）。source partial 只诊断，不通过缓存入口生成USD港币收益。

## 独立真实离线核对

```bash
.venv/bin/python scripts/verify_daily_hkd.py --s01-manifest outputs/acceptance/S01/snapshots/20261012T143920Z-6f4d426f/snapshot_manifest.json --output outputs/acceptance/S04C2/legacy_replay
.venv/bin/python -m pytest -q
```

旧原始快照：`20261012T143920Z-6f4d426f`，所有原始文件先按manifest核验哈希。此入口是显式原始文件导入后的端点诊断，不是将旧partial快照发布成success。FX全部历史观察及缺失保留，元数据`source_global_status=partial`、`source_scope`明确本窗口端点；没有设置`source_status=success`，不改严格缓存入口规则。

| 2025-01 | 期初实际日 | 期末实际日 | 原币收益 | FX收益 | 港币收益 |
| --- | --- | --- | --- | --- | --- |
| SPY价格 | 2024-12-31 | 2025-01-31 | 2.6856237778% | 0.3632340043% | 3.0586128809% |
| 2800.HK价格 | 2024-12-31 | 2025-01-28 | 1.0869455644% | 0%（固定1） | 1.0869455644% |

SPY的FX实际日期为2024-12-31和2025-01-31，分别为7.763500213623047和7.7916998863220215 HKD/USD，年龄均0。独立脚本直接读取原始JSON及London日期，独立筛选端点并计算比值，与生产结果在数值精度范围一致；故意篡改HKD结果的测试会失败。

证据：[独立核对JSON](legacy_replay/independent_verification.json)、[原始FX端点参考](legacy_replay/raw_fx_endpoint_reference.csv)、[生产端点](legacy_replay/fx_endpoints.csv)、[逐行FX诊断](legacy_replay/fx_observations.csv)、[SPY对照](legacy_replay/SPY_reconciliation.csv)、[2800.HK对照](legacy_replay/2800.HK_reconciliation.csv)。价格和汇率原文件SHA均在各产品metadata及JSON中，不以下载或日历收市时间填available_at。

## 检查证据

- [基线检查](baseline_tests.txt)：360项通过。
- [核心报告](task-1-report.md)、[核心审查](task-1-review.md)：79项相关检查，spec/quality Approved。
- [界面报告](task-2-report.md)、[界面审查](task-2-review.md)：34项相关检查，spec/quality Approved。
- [独立脚本报告](task-3-report.md)：5项检查，真实离线CLI exit0。
- [最终全套检查](full_tests.txt)：**445 passed**，2个既有日历依赖DeprecationWarnings，30.38秒，exit0。初版420项记录另保留，不替代最终检查。
- [浏览器检查](browser_checks.json)、[缺FX检查](browser_extra_checks.json)：1440/720宽度无页面横向溢出或框架异常，确认撤下旧结果，缺月0个可预览月；实际原生下载CSV数值及端点/历史标记已独立读取确认。
- [宽屏](browser_1440.png)、[窄屏](browser_720.png)、[成功结果](browser_result.png)、[未确认阻止](browser_blocked.png)、[缺月阻止](browser_missing_fx.png)、[原生下载CSV](browser_exports/verified_reconciliation.csv)。已人工查看关键截图，未见标题/控件文字重叠。
- [包重装](package_install.txt)：标准安装，无依赖升级；104项锁定版本匹配，pip check无损坏依赖，全部26个源码模块与已安装文件字节一致。
- 输入数据34个文件字节保持不变，当前价格/参考快照全部通过原manifest哈希；两个下载目录运行列表未增加，页面操作不联网。

浏览器自动化曾因React Aria选择器及视口切换时鼠标位置过早计算而失败；最终组合框采用原生键盘交互避免坐标波动；只调整验收脚本，最终上述记录通过，没有因此修改产品逻辑。原生上传由AppTest替代传输层，实际CSV/XLSX解析和页面状态过程运行；不宣称真实浏览器文件选择已自动验证。

最终审查初版4项Important（价格/FX空时间戳、FX原始行号、auditor证据交叉检查）均已补失败检查并修复；超大整数时间戳亦失败关闭为ValueError。共享parser既有行为不变，两个缓存入口复用guard。[修复报告](final-fix-report.md)、[最终审查Approved](final-review.md)、[最终离线重放](final_replay.txt)、[完整性核验](final_integrity_checks.json)可复查。工作台最终监听PID72574，健康接口正常；没有更改依赖或原始数据。

## 仍有的限制与下一步

结果是当前版本价格及异步日线FX估值预览，`available_at`为空、`historical_eligible=False`。S04-C3仍需独立处理历史可得证据，S04整体及S05候选池未验收。没有计算组合风险、utility、相关性或正式持仓。

缓存列表对任何损坏manifest采取保守阻止策略，未选记录损坏也可能导致该来源不可用；先修复损坏记录后再使用。现有两个calendar/NumPy弃用提示留待依赖维护，不全局屏蔽。本轮没有新在线请求；HKMA在线与最近C1行情请求失败状态保持原样。未新增付费接口。
